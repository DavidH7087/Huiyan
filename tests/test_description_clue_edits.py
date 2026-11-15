"""Editable description-only screening and backwards-compatible migrations."""
import sqlite3

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.storage import Store


def _upload(client, task_id):
    response=client.post(f'/api/tasks/{task_id}/resumes',files=[
        ('files',('one.txt','张三\n曾独立负责客户开发和制造业大客户项目。'.encode('utf8'),'text/plain'))
    ])
    assert response.status_code == 200 and response.json()['imported']==1


def test_hr_can_remove_automatic_clues_without_deleting_original_description(tmp_path):
    with TestClient(create_app(tmp_path/'data')) as client:
        suggested=client.post('/api/criteria/suggest',json={
            'description':'寻找有客户开发经验；最好熟悉制造业'
        }).json()
        assert '客户开发' in suggested['description_leads']
        task=client.post('/api/tasks',json={
            'title':'销售岗位', 'description':'寻找有客户开发经验；最好熟悉制造业',
            'description_leads': [], 'required': [], 'preferred': []
        }).json()
        assert task['description_leads']==[]
        _upload(client,task['id'])
        run=client.post(f'/api/tasks/{task["id"]}/runs',json={}).json()
        assert run['criteria']['description_leads']==[]
        assert run['criteria']['required']==[]
        assert run['criteria']['preferred']==[]
        assert client.get(f'/api/tasks/{task["id"]}').json()['description'].startswith('寻找')


def test_revised_clues_only_affect_subsequent_rounds(tmp_path):
    with TestClient(create_app(tmp_path/'data')) as client:
        task=client.post('/api/tasks',json={
            'title':'销售岗位','description':'要求客户开发',
            'required':['客户开发'], 'description_leads':['制造业']
        }).json()
        _upload(client,task['id'])
        url=f'/api/tasks/{task["id"]}'
        old=client.post(url+'/runs',json={}).json()
        updated=client.patch(url,json={'description_leads':['渠道拓展'],'required':['Java']})
        assert updated.status_code==200
        fresh=client.post(url+'/runs',json={}).json()
        old_criteria=client.get(url+f'/runs/{old["id"]}/results').json()['run']['criteria']
        assert old_criteria['description_leads']==['制造业']
        assert old_criteria['required']==['客户开发']
        assert fresh['criteria']['description_leads']==['渠道拓展']
        assert fresh['criteria']['required']==['Java']


def test_task_schema_adds_clues_without_erasing_legacy_data(tmp_path):
    with sqlite3.connect(tmp_path/'huiyan.sqlite3') as connection:
        connection.execute("""CREATE TABLE tasks (
          id INTEGER PRIMARY KEY, title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '', required TEXT NOT NULL DEFAULT '[]',
          preferred TEXT NOT NULL DEFAULT '[]',
          excluded TEXT NOT NULL DEFAULT '[]', match_mode TEXT NOT NULL DEFAULT 'aliases',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          archived INTEGER NOT NULL DEFAULT 0
        )""")
        connection.execute("INSERT INTO tasks(title,description) VALUES('旧任务','客户开发')")
    store=Store(tmp_path)
    with store.connect() as connection:
        row=connection.execute('SELECT * FROM tasks').fetchone()
        assert row['title']=='旧任务'
        assert row['description_leads'] is None
