from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app


def test_delete_requires_archival_and_exact_name_then_removes_data(tmp_path):
    app=create_app(tmp_path/'db')
    with TestClient(app) as c:
        task=c.post('/api/tasks',json={'title':'销售经理','required':['客户开发']}).json()['id']
        upload=c.post(f'/api/tasks/{task}/resumes',files=[('files',('a.txt','张三\n客户开发'.encode(),'text/plain'))])
        assert upload.json()['imported']==1
        person=c.get(f'/api/tasks/{task}/resumes').json()[0]['id']
        run1=c.post(f'/api/tasks/{task}/runs',json={}).json()['id']
        run2=c.post(f'/api/tasks/{task}/runs',json={'name':'第二轮','scope':'parent','parent_id':run1}).json()['id']
        c.patch(f'/api/tasks/{task}/resumes/{person}/review',json={'status':'加入面试名单','note':'已人工审核'})
        history=c.get(f'/api/tasks/{task}/review-history').json()
        assert len(history)==1 and history[0]['status']=='加入面试名单'
        assert c.request('DELETE',f'/api/tasks/{task}',json={'confirm_title':'销售经理'}).status_code==409
        c.patch(f'/api/tasks/{task}',json={'archived':True})
        assert c.request('DELETE',f'/api/tasks/{task}',json={'confirm_title':'错误任务名'}).status_code==400
        with app.state.store.connect() as conn:
            filename=conn.execute('SELECT stored_file FROM resumes WHERE id=?',(person,)).fetchone()[0]
        assert (app.state.store.root/'uploads'/filename).exists()
        outcome=c.request('DELETE',f'/api/tasks/{task}',json={'confirm_title':'销售经理'})
        assert outcome.status_code==200
        assert outcome.json()['files_pending_cleanup']==0
        assert c.get(f'/api/tasks/{task}').status_code==404
        assert not (app.state.store.root/'uploads'/filename).exists()
        with app.state.store.connect() as conn:
            for table in ('tasks','resumes','resume_profiles','runs','evaluations','reviews','review_events','imports'):
                assert conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0


def test_review_history_is_task_isolated(tmp_path):
    app=create_app(tmp_path/'separate')
    with TestClient(app) as c:
        a=c.post('/api/tasks',json={'title':'A'}).json()['id']
        b=c.post('/api/tasks',json={'title':'B'}).json()['id']
        assert c.get(f'/api/tasks/{a}/review-history').json()==[]
        assert c.get(f'/api/tasks/{b}/review-history').json()==[]
