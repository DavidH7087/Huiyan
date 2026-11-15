"""Protected screening contract: optional evidence flags never auto-delete candidates."""
import sqlite3
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.engine import evaluate
from backend.storage import Store


def test_exact_keywords_do_not_expand_industry_synonyms():
    pages = [{'page': 1, 'source': 'txt', 'text': '负责工业品销售及开发客户，参加渠道项目。'}]
    fuzzy = evaluate(['B2B销售'], [], pages)
    exact = evaluate(['B2B销售'], [], pages, match_mode='exact')
    assert fuzzy['group'] == '优先查看'
    assert exact['group'] == '需要确认'
    assert exact['required_met_textually'] == 0


def test_exclusion_is_review_flag_only_and_keeps_resume():
    pages = [{'page': 1, 'source': 'txt', 'text': '负责 B2B 销售。 曾承担短期兼职岗位。'}]
    result = evaluate(['B2B销售'], [], pages, excluded=['兼职'])
    assert result['group'] == '需要确认'
    assert result['exclusion_flags'] == 1
    assert result['required_met_textually'] == 1
    assert any(c['kind'] == 'excluded' and c['state'] == '排除线索待人工核实' for c in result['checks'])
    without_flag = evaluate(['B2B销售'], [], [{'page':1,'text':'负责 B2B 销售，没有兼职经历。'}], excluded=['兼职'])
    assert without_flag['exclusion_flags'] == 0
    assert without_flag['group'] == '优先查看'


def test_ocr_exclusion_is_uncertain_and_cannot_delete():
    data = evaluate(['Java'], [], [{'page':1,'text':'Java 后端开发，曾做兼职。', 'source':'ocr'}], excluded=['兼职'])
    assert data['group'] == '需要确认'
    assert data['exclusion_flags'] == 1
    assert data['checks'][-1]['state'] == 'OCR排除线索待核实'


def test_excluded_keywords_persist_in_task_and_immutable_round(tmp_path):
    with TestClient(create_app(tmp_path/'app')) as client:
        task = client.post('/api/tasks', json={
            'title':'销售招聘', 'required':['B2B销售'], 'preferred':['制造业'],
            'excluded':['兼职'], 'match_mode':'exact'
        })
        assert task.status_code == 200, task.text
        task_id = task.json()['id']
        assert task.json()['excluded'] == ['兼职']
        assert task.json()['match_mode'] == 'exact'
        for filename, content in [('a.txt','应聘者甲\n负责 B2B 销售，承担过兼职工作。'),
                                   ('b.txt','应聘者乙\n负责 B2B 销售。')]:
            res=client.post(f'/api/tasks/{task_id}/resumes', files=[('files',(filename,content.encode('utf-8'),'text/plain'))])
            assert res.json()['imported'] == 1
        first=client.post(f'/api/tasks/{task_id}/runs', json={'name':'第一轮'}).json()
        results=client.get(f'/api/tasks/{task_id}/runs/{first["id"]}/results').json()
        records=results['results']
        assert len(records)==2
        assert results['run']['criteria']['excluded']==['兼职']
        assert results['run']['criteria']['match_mode']=='exact'
        flagged=[r for r in records if r['evaluation']['exclusion_flags']]
        assert len(flagged)==1 and flagged[0]['evaluation']['group']=='需要确认'
        assert next(r for r in records if not r['evaluation']['exclusion_flags'])['evaluation']['group']=='优先查看'
        changed=client.patch(f'/api/tasks/{task_id}', json={'excluded':['外包'],'match_mode':'aliases'})
        assert changed.status_code==200
        historic=client.get(f'/api/tasks/{task_id}/runs/{first["id"]}/results').json()
        assert historic['run']['criteria']['excluded']==['兼职']
        assert historic['run']['criteria']['match_mode']=='exact'
        excel=client.get(f'/api/tasks/{task_id}/runs/{first["id"]}/export')
        assert excel.status_code==200
        from openpyxl import load_workbook
        import io
        sheet=load_workbook(io.BytesIO(excel.content)).active
        assert '排除线索' in ' '.join(str(cell.value) for cell in sheet[1])


def test_existing_sqlite_task_schema_migrated_without_erasing_history(tmp_path):
    db=tmp_path/'huiyan.sqlite3'
    with sqlite3.connect(db) as cn:
        cn.execute('''CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', required TEXT NOT NULL DEFAULT '[]',
            preferred TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL DEFAULT (datetime('now')),
            archived INTEGER NOT NULL DEFAULT 0
        )''')
        cn.execute("INSERT INTO tasks (title,required) VALUES ('历史岗位','[\"Java\"]')")
    store=Store(tmp_path)
    with store.connect() as cn:
        task=cn.execute('SELECT * FROM tasks').fetchone()
        assert task['title']=='历史岗位'
        assert task['excluded']=='[]'
        assert task['match_mode']=='aliases'
