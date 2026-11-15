"""Privacy operations report without destructive automatic cleanup."""
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.diagnostics import inspect_local_data


def test_retention_preview_does_not_delete_candidate(tmp_path):
    with TestClient(create_app(tmp_path/'data')) as client:
        task=client.post('/api/tasks',json={'title':'工程师'}).json()['id']
        url=f'/api/tasks/{task}'
        client.post(url+'/resumes',files=[
            ('files',('cv.txt','张三\n有 Python 工作经验'.encode(),'text/plain'))
        ])
        with client.app.state.store.connect() as cn:
            cn.execute("UPDATE resumes SET imported_at=? WHERE task_id=?",
                       ((datetime.utcnow()-timedelta(days=400)).strftime('%Y-%m-%d %H:%M:%S'),task))
        response=client.get(url+'/retention?days=365')
        assert response.status_code==200,response.text
        report=response.json()
        assert report['due_count']==1
        assert report['manual_review_required'] is True
        assert len(client.get(url+'/resumes').json())==1
        assert client.get(url+'/retention?days=1').status_code==422
        assert client.get(url+'/retention?days=9999').status_code==422


def test_local_diagnostics_count_missing_and_orphan_without_leaking_names(tmp_path):
    with TestClient(create_app(tmp_path/'local')) as client:
        task=client.post('/api/tasks',json={'title':'工程师'}).json()['id']
        client.post(f'/api/tasks/{task}/resumes',files=[
            ('files',('cv.txt','张三\n客户开发'.encode(),'text/plain'))
        ])
        root=client.app.state.store.root
        report=inspect_local_data(root)
        assert report['ok'] and report['resume_count']==1
        assert client.get('/api/system/diagnostics').status_code==403
        saved=next((root/'uploads').iterdir())
        saved.unlink()
        report=inspect_local_data(root)
        assert not report['ok'] and report['missing_files']==1
        assert 'cv.txt' not in str(report)
