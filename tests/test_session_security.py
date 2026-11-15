from fastapi.testclient import TestClient
from backend.app import create_app


def test_session_cookie_required_for_local_candidate_api(tmp_path, monkeypatch):
    monkeypatch.setenv('HUIYAN_DESKTOP_MODE', '1')
    monkeypatch.setenv('HUIYAN_SESSION_TOKEN', 'synthetic-unguessable-session-token-for-test')
    app=create_app(tmp_path/'data')
    with TestClient(app, base_url='http://127.0.0.1:12345') as client:
        assert client.get('/api/health').status_code == 200
        assert client.get('/api/tasks').status_code == 401
        assert client.post('/api/tasks',json={'title':'test'}).status_code == 401
        assert client.get('/?session=incorrect-token', follow_redirects=False).status_code == 401
        login=client.get('/?session=synthetic-unguessable-session-token-for-test',
                         follow_redirects=False)
        assert login.status_code == 303
        assert 'httponly' in login.headers['set-cookie'].lower()
        assert 'samesite=strict' in login.headers['set-cookie'].lower()
        assert client.get('/api/tasks').status_code == 200
        task=client.post('/api/tasks',json={'title':'虚构测试任务','required':['Java']})
        assert task.status_code == 200
        assert len(client.get('/api/tasks').json()) == 1
        # A fresh browser with no cookie cannot enumerate candidate metadata.
        with TestClient(app,base_url='http://127.0.0.1:12345') as stranger:
            assert stranger.get('/api/tasks').status_code == 401
            assert stranger.get('/api/tasks/1').status_code == 401
            assert stranger.get('/api/tasks/1/resumes/1/original').status_code == 401


def test_cross_site_origin_is_rejected_even_if_cookie_is_set(tmp_path,monkeypatch):
    monkeypatch.setenv('HUIYAN_DESKTOP_MODE','1')
    monkeypatch.setenv('HUIYAN_SESSION_TOKEN','test-long-random-token')
    with TestClient(create_app(tmp_path/'data'),base_url='http://127.0.0.1:12345') as client:
        client.get('/?session=test-long-random-token')
        result=client.post('/api/tasks',json={'title':'测试'},headers={'Origin':'https://attacker.invalid'})
        assert result.status_code == 403


def test_development_mode_remains_accessible_without_desktop_token(tmp_path,monkeypatch):
    monkeypatch.delenv('HUIYAN_DESKTOP_MODE',raising=False)
    monkeypatch.delenv('HUIYAN_SESSION_TOKEN',raising=False)
    with TestClient(create_app(tmp_path/'cloud')) as client:
        assert client.get('/').status_code == 200
        assert client.get('/api/tasks').status_code == 200
