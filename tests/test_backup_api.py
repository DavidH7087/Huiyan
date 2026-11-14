import io

from fastapi.testclient import TestClient
from backend.app import create_app
from backend.backup import MAGIC, restore_to_new_directory


def test_desktop_backup_download_and_restore(tmp_path, monkeypatch):
    monkeypatch.setenv('HUIYAN_DESKTOP_MODE', '1')
    app = create_app(tmp_path / 'desktop')
    with TestClient(app, base_url='http://127.0.0.1:12345') as client:
        task_id = client.post('/api/tasks', json={'title': '模拟销售招聘', 'required':['客户开发']}).json()['id']
        upload = client.post(f'/api/tasks/{task_id}/resumes', files=[
            ('files', ('synthetic.txt', '虚构测试\n负责客户开发'.encode(), 'text/plain'))])
        assert upload.json()['imported'] == 1
        response = client.post('/api/system/backup', json={'password': 'a-very-long-test-password'})
        assert response.status_code == 200, response.text
        assert response.headers['cache-control'] == 'no-store'
        assert response.content.startswith(MAGIC)
        assert '虚构测试'.encode('utf-8') not in response.content
        file = tmp_path / 'export.hyb'
        file.write_bytes(response.content)
        restore_to_new_directory(file, 'a-very-long-test-password', tmp_path / 'restored')
        restored_app = create_app(tmp_path / 'restored')
        with TestClient(restored_app, base_url='http://127.0.0.1:20000') as restored:
            assert restored.get('/api/tasks').json()[0]['title'] == '模拟销售招聘'
            assert len(restored.get(f'/api/tasks/{task_id}/resumes').json()) == 1


def test_codespace_cannot_export_server_backups(tmp_path, monkeypatch):
    monkeypatch.delenv('HUIYAN_DESKTOP_MODE', raising=False)
    app = create_app(tmp_path / 'cloud')
    with TestClient(app) as client:
        assert client.get('/api/health').json()['backup_available'] is False
        assert client.post('/api/system/backup', json={'password': 'long-password-123456'}).status_code == 403
