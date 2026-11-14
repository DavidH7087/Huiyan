from fastapi.testclient import TestClient
from backend.app import create_app


def test_desktop_accepts_local_requests_and_rejects_cross_site(tmp_path, monkeypatch):
    monkeypatch.setenv('HUIYAN_DESKTOP_MODE', '1')
    app = create_app(tmp_path / 'desktop')
    with TestClient(app, base_url='http://127.0.0.1:13579') as client:
        assert client.get('/api/health').status_code == 200
        assert client.post('/api/tasks', json={'title': '测试招聘'},
            headers={'origin': 'http://127.0.0.1:13579', 'sec-fetch-site': 'same-origin'}).status_code == 200
        assert client.post('/api/tasks', json={'title': '非法请求'},
            headers={'origin': 'https://attacker.invalid', 'sec-fetch-site': 'cross-site'}).status_code == 403
        assert client.get('/api/tasks', headers={'Host':'fake.example', 'origin':'http://fake.example'}).status_code == 403
        assert client.get('/api/tasks', headers={'sec-fetch-site': 'cross-site'}).status_code == 403
        assert len(client.get('/api/tasks').json()) == 1


def test_codespace_mode_does_not_force_local_host_only(tmp_path, monkeypatch):
    monkeypatch.delenv('HUIYAN_DESKTOP_MODE', raising=False)
    app = create_app(tmp_path / 'codespace')
    with TestClient(app) as client:
        assert client.get('/api/health', headers={'Host':'example.preview.app.github.dev'}).status_code == 200
