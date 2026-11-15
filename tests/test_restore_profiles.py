"""End-to-end restoration tests use fictional candidate files only."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.backup import MAGIC
from backend.restore_profiles import (active_data_directory, profile_status,
                                      schedule_original_profile)


def _create_archive(tmp_path, monkeypatch):
    monkeypatch.setenv('HUIYAN_DESKTOP_MODE', '1')
    home = tmp_path / 'Huiyan'
    root = home / 'data'
    app = create_app(root)
    with TestClient(app, base_url='http://127.0.0.1:12345') as client:
        t = client.post('/api/tasks', json={'title': '虚构销售测试', 'required': ['客户开发']}).json()
        reply = client.post(f'/api/tasks/{t["id"]}/resumes', files=[
            ('files', ('candidate.txt', '姓名：示例甲\n熟悉企业客户开发'.encode(), 'text/plain'))
        ])
        assert reply.json()['imported'] == 1
        backup = client.post('/api/system/backup', json={'password': 'long-fixture-password-2026'})
        assert backup.status_code == 200
        assert backup.content.startswith(MAGIC)
    return root, backup.content


def test_user_recovers_to_new_profile_without_overwriting_original(tmp_path, monkeypatch):
    root, contents = _create_archive(tmp_path, monkeypatch)
    original_bytes = (root / 'huiyan.sqlite3').read_bytes()
    with TestClient(create_app(root), base_url='http://127.0.0.1:12345') as client:
        response = client.post('/api/system/restore', data={
            'password': 'long-fixture-password-2026', 'confirm': '恢复'},
            files={'file': ('backup.hyb', contents, 'application/octet-stream')})
        assert response.status_code == 200, response.text
        info = response.json()
        assert info['original_preserved'] and info['restart_required']
        assert info['restored_files'] == 1
        assert client.get('/api/tasks').json()[0]['title'] == '虚构销售测试'
        status = client.get('/api/system/profiles').json()
        assert status['pending_profile'] == info['profile']
    assert (root / 'huiyan.sqlite3').read_bytes() == original_bytes
    restored = active_data_directory(root.parent)
    assert restored != root
    with TestClient(create_app(restored), base_url='http://127.0.0.1:12345') as new_client:
        assert new_client.get('/api/tasks').json()[0]['title'] == '虚构销售测试'
        assert len(new_client.get('/api/tasks/1/resumes').json()) == 1
        status = new_client.get('/api/system/profiles').json()
        assert status['can_return_to_original'] is True
        back = new_client.post('/api/system/profile/original')
        assert back.status_code == 200
        assert back.json()['restart_required']
    assert active_data_directory(root.parent) == root
    assert restored.is_dir(), 'switching back must not erase recovered profile'


def test_wrong_password_does_not_replace_active_archive(tmp_path, monkeypatch):
    root, contents = _create_archive(tmp_path, monkeypatch)
    with TestClient(create_app(root), base_url='http://127.0.0.1:12345') as client:
        bad = client.post('/api/system/restore', data={'password':'wrong-password-123456', 'confirm':'恢复'},
                          files={'file':('wrong.hyb', contents, 'application/octet-stream')})
        assert bad.status_code == 400, bad.text
        assert '密码' in bad.json()['detail']
        assert client.post('/api/system/restore', data={'password': 'long-fixture-password-2026',
                                                        'confirm': 'cancel'},
                           files={'file': ('backup.hyb', contents)}).status_code == 400
    assert active_data_directory(root.parent) == root
    assert not list(root.parent.glob('restored-*'))


def test_cloud_mode_cannot_restore_or_select_profiles(tmp_path, monkeypatch):
    monkeypatch.delenv('HUIYAN_DESKTOP_MODE', raising=False)
    with TestClient(create_app(tmp_path / 'data')) as client:
        assert client.get('/api/system/profiles').status_code == 403
        assert client.post('/api/system/restore',data={'password':'a'*15,'confirm':'恢复'},
                           files={'file':('test.hyb',b'irrelevant')}).status_code == 403
        assert client.post('/api/system/profile/original').status_code == 403


def test_invalid_profile_config_fails_loudly(tmp_path):
    home = tmp_path / 'Huiyan'; home.mkdir()
    (home / 'active-profile.json').write_text('{"version":1,"profile":"../outside"}')
    import pytest
    from backend.backup import BackupError
    with pytest.raises(BackupError):
        active_data_directory(home)


def test_empty_or_corrupt_backups_cannot_stage_restore(tmp_path, monkeypatch):
    root, _ = _create_archive(tmp_path, monkeypatch)
    with TestClient(create_app(root), base_url='http://127.0.0.1:12345') as client:
        bad = client.post('/api/system/restore', data={'password':'long-fixture-password-2026','confirm':'恢复'},
                          files={'file':('broken.hyb', b'not a backup')})
        assert bad.status_code == 400
    assert active_data_directory(root.parent) == root
