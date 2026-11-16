"""Names are extracted from the résumé text, never inferred from a filename."""
import io
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from docx import Document
from openpyxl import load_workbook

from backend.app import create_app
from backend.parsing import extract_identity, extract_pages


@pytest.mark.parametrize(('resume_text','expected'), [
    ('姓 名：李小明\n工作经历：负责客户开发', '李小明'),
    ('姓名 | 王小芳 | 电话：13800138000', '王小芳'),
    ('姓名 赵四\n技能：Python', '赵四'),
    ('个人简历\n张 三\n3年销售经验', '张三'),
    ('Name: Alice Johnson\nExperience: 3 years', 'Alice Johnson'),
    ('Full Name：Sarah Chen\nSkills: Excel', 'Sarah Chen'),
    ('王小明\n教育经历：本科', '王小明'),
    ('工作经历\n负责 B2B 销售\n制造业客户开发', '姓名待确认'),
    ('应聘岗位：销售经理\n联系电话：13800138000', '姓名待确认'),
])
def test_name_is_taken_from_content(resume_text,expected):
    result=extract_identity([{'page':1,'text':resume_text}],'some-opaque-file-17.pdf')
    assert result['name']==expected
    assert result['name_source']==('unknown' if expected=='姓名待确认' else 'extracted')


def test_docx_table_candidate_name_is_visible():
    doc=Document()
    table=doc.add_table(rows=1,cols=2)
    table.cell(0,0).text='姓名'
    table.cell(0,1).text='李小明'
    doc.add_paragraph('教育背景：本科\n3年销售工作经验')
    stream=io.BytesIO()
    doc.save(stream)
    pages=extract_pages('invoice-like-id.docx',stream.getvalue())
    assert extract_identity(pages,'invoice-like-id.docx')['name']=='李小明'


def test_legacy_filename_names_upgrade_without_damaging_runs_or_reviews(tmp_path):
    app=create_app(tmp_path/'saved')
    with TestClient(app) as client:
        tid=client.post('/api/tasks',json={'title':'客户经理','required':['客户开发']}).json()['id']
        prefix=f'/api/tasks/{tid}'
        incoming=client.post(prefix+'/resumes',files=[
            ('files',('SYN-0001-doc.txt','姓名：王小明\n负责客户开发'.encode('utf-8'),'text/plain')),
            ('files',('SYN-0002-doc.txt','姓名：李小芳\n负责行政支持'.encode('utf-8'),'text/plain')),
        ])
        assert incoming.json()['imported']==2
        rows=client.get(prefix+'/resumes').json()
        first=rows[0]['id']
        result=client.post(prefix+'/runs',json={'name':'初筛'}).json()
        run_id=result['id']
        review=client.patch(prefix+f'/resumes/{first}/review',json={
            'status':'加入面试名单','note':'已确认工作经历'
        })
        assert review.status_code==200
        with app.state.store.connect() as db:
            for row in rows:
                db.execute("UPDATE resumes SET name=?,name_source='legacy' WHERE id=?",
                           (Path(row['filename']).stem,row['id']))
            before=db.execute('SELECT results_json FROM evaluations WHERE run_id=? AND resume_id=?',
                              (run_id,first)).fetchone()[0]
        # Merely opening an old run migrates only display names, not run evaluations.
        result=client.get(prefix+f'/runs/{run_id}/results').json()
        names={x['name'] for x in result['results']}
        assert names=={'王小明','李小芳'}
        assert all(x['name_source']=='extracted' for x in result['results'])
        assert client.get(prefix+f'/resumes/{first}').json()['name'] == '李小芳'
        assert client.get(prefix+f'/resumes').json()[0]['name'] in names
        assert client.get(prefix+f'/resumes/{first}/original').status_code==404
        output=client.get(prefix+f'/runs/{run_id}/export')
        book=load_workbook(io.BytesIO(output.content))
        assert {book.active['A2'].value,book.active['A3'].value}==names
        with app.state.store.connect() as db:
            after=db.execute('SELECT results_json FROM evaluations WHERE run_id=? AND resume_id=?',
                             (run_id,first)).fetchone()[0]
        assert before==after
        assert client.get(prefix+f'/runs/{run_id}/results').json()['results'][0]['review_note'] or client.get(prefix+f'/runs/{run_id}/results').json()['results'][1]['review_note']


def test_name_is_editable_and_not_overwritten_by_later_requests(tmp_path):
    app=create_app(tmp_path/'edited')
    with TestClient(app) as client:
        a=client.post('/api/tasks',json={'title':'岗位 A'}).json()['id']
        b=client.post('/api/tasks',json={'title':'岗位 B'}).json()['id']
        prefix=f'/api/tasks/{a}'
        imported=client.post(prefix+'/resumes',files=[
            ('files',('opaque-name.txt','客户关系管理\n工作经历：负责销售支持'.encode('utf-8'),'text/plain'))
        ])
        assert imported.json()['imported']==1
        row=client.get(prefix+'/resumes').json()[0]
        assert row['name']=='姓名待确认'
        assert row['name_source']=='unknown'
        changed=client.patch(prefix+f'/resumes/{row["id"]}/name',json={'name':' 张小明 '})
        assert changed.status_code==200
        assert changed.json()['name']=='张小明'
        assert changed.json()['name_source']=='manual'
        assert client.patch(prefix+f'/resumes/{row["id"]}/name',json={'name':'   '}).status_code==422
        assert client.patch(f'/api/tasks/{b}/resumes/{row["id"]}/name',json={'name':'其他人'}).status_code==404
        run=client.post(prefix+'/runs',json={}).json()
        assert client.get(prefix+f'/runs/{run["id"]}/results').json()['results'][0]['name']=='张小明'
        assert client.get(prefix+f'/resumes/{row["id"]}').json()['name_source']=='manual'
        export=client.get(prefix+f'/runs/{run["id"]}/export')
        assert load_workbook(io.BytesIO(export.content)).active['A2'].value=='张小明'
        with app.state.store.connect() as db:
            assert db.execute('SELECT name_source FROM resumes WHERE id=?',(row['id'],)).fetchone()[0]=='manual'


def test_preexisting_database_receives_name_source_column(tmp_path):
    root=tmp_path/'legacy'
    root.mkdir()
    with sqlite3.connect(root/'huiyan.sqlite3') as db:
        db.execute("""CREATE TABLE resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,task_id INTEGER NOT NULL,
            filename TEXT NOT NULL, content_hash TEXT NOT NULL,
            stored_file TEXT NOT NULL,name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',email TEXT NOT NULL DEFAULT '',
            pages_json TEXT NOT NULL,imported_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""")
    app=create_app(root)
    with app.state.store.connect() as db:
        columns={row['name'] for row in db.execute('PRAGMA table_info(resumes)')}
        assert 'name_source' in columns
