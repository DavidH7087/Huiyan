"""Candidate-level personal data deletion with preserved task and unrelated people."""
from fastapi.testclient import TestClient
from backend.app import create_app


def test_delete_single_candidate_and_all_corresponding_records(tmp_path):
    app = create_app(tmp_path / 'data')
    with TestClient(app) as client:
        task = client.post('/api/tasks', json={'title':'虚构招聘项目','required':['客户开发']}).json()['id']
        files = [('files', (f'fictional-{i}.txt', f'虚构候选人{i}\n负责客户开发'.encode('utf-8'), 'text/plain')) for i in (1,2)]
        uploaded = client.post(f'/api/tasks/{task}/resumes', files=files).json()
        assert uploaded['imported'] == 2
        people = client.get(f'/api/tasks/{task}/resumes').json()
        target = next(r for r in people if r['filename']=='fictional-1.txt')
        keeper = next(r for r in people if r['filename']=='fictional-2.txt')
        first = client.post(f'/api/tasks/{task}/runs', json={'name':'首次筛选'}).json()['id']
        client.post(f'/api/tasks/{task}/runs', json={'name':'二次筛选','scope':'parent','parent_id':first})
        client.patch(f'/api/tasks/{task}/resumes/{target["id"]}/review',json={'status':'加入面试名单','note':'虚构人工备注'})
        with app.state.store.connect() as db:
            path = app.state.store.root/'uploads'/db.execute(
                'SELECT stored_file FROM resumes WHERE id=?',(target['id'],)).fetchone()[0]
        assert path.exists()
        url = f'/api/tasks/{task}/resumes/{target["id"]}'
        assert client.request('DELETE',url,json={'confirm_filename':'错误文件名'}).status_code == 400
        assert path.exists()
        result=client.request('DELETE',url,json={'confirm_filename':'fictional-1.txt'})
        assert result.status_code == 200, result.text
        assert result.json()['deleted']
        assert result.json()['history_adjusted']
        assert result.json()['files_pending_cleanup'] == 0
        assert not path.exists()
        assert client.get(url).status_code == 404
        assert client.get(f'/api/tasks/{task}').json()['resume_count'] == 1
        assert client.get(f'/api/tasks/{task}/runs/{first}/results').json()['total'] == 1
        assert client.get(f'/api/tasks/{task}/resumes/{keeper["id"]}').status_code == 200
        assert client.get(f'/api/tasks/{task}/review-history').json() == []
        with app.state.store.connect() as db:
            assert db.execute('SELECT COUNT(*) FROM redaction_events WHERE task_id=?',(task,)).fetchone()[0] == 1
            assert db.execute('SELECT COUNT(*) FROM evaluations WHERE resume_id=?',(target['id'],)).fetchone()[0] == 0
            assert db.execute('SELECT COUNT(*) FROM imports WHERE task_id=? AND filename=?',(task,'fictional-1.txt')).fetchone()[0] == 0
        assert client.request('DELETE',url,json={'confirm_filename':'fictional-1.txt'}).status_code == 404
