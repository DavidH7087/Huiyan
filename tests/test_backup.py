"""Use only fictitious document bytes for backup tests."""
import sqlite3
from pathlib import Path

import pytest

from backend.backup import BackupError, create_encrypted_backup, restore_to_new_directory


def create_data(root: Path):
    (root / 'uploads').mkdir(parents=True)
    db = root / 'huiyan.sqlite3'
    with sqlite3.connect(db) as c:
        c.executescript('''CREATE TABLE resumes (stored_file TEXT NOT NULL);
                          CREATE TABLE review_events (status TEXT NOT NULL);''')
        filename = 'a' * 32 + '.txt'
        c.execute('INSERT INTO resumes VALUES (?)', (filename,))
        c.execute('INSERT INTO review_events VALUES (?)', ('加入面试名单',))
    (root / 'uploads' / filename).write_text('完全虚构：测试简历，负责企业客户开发', encoding='utf-8')


def test_encrypted_backup_restore_and_integrity(tmp_path):
    root = tmp_path / 'original'
    create_data(root)
    dest = tmp_path / 'archive.hyb'
    result = create_encrypted_backup(root, 'long-secret-test-password-2026', dest)
    assert result['documents'] == 1
    assert b'\xe5\xae\xa2\xe6\x88\xb7' not in dest.read_bytes()
    output = tmp_path / 'restored'
    restore = restore_to_new_directory(dest, 'long-secret-test-password-2026', output)
    assert restore['restored_files'] == 1
    assert list((output / 'uploads').iterdir())[0].read_bytes() == list((root / 'uploads').iterdir())[0].read_bytes()
    with sqlite3.connect(output / 'huiyan.sqlite3') as c:
        assert c.execute('SELECT status FROM review_events').fetchone()[0] == '加入面试名单'
    with pytest.raises(BackupError, match='已经存在'):
        restore_to_new_directory(dest, 'long-secret-test-password-2026', output)


def test_wrong_password_and_tamper_fail_closed(tmp_path):
    root = tmp_path / 'original'
    create_data(root)
    dest = tmp_path / 'archive.hyb'
    create_encrypted_backup(root, 'long-secret-test-password-2026', dest)
    with pytest.raises(BackupError, match='密码错误'):
        restore_to_new_directory(dest, 'wrong-password-123456', tmp_path / 'failed')
    assert not (tmp_path / 'failed').exists()
    data = bytearray(dest.read_bytes())
    data[len(data)//2] ^= 1
    dest.write_bytes(data)
    with pytest.raises(BackupError, match='篡改'):
        restore_to_new_directory(dest, 'long-secret-test-password-2026', tmp_path / 'tampered')
    assert not (tmp_path / 'tampered').exists()


def test_weak_password_rejected_without_output(tmp_path):
    root = tmp_path / 'original'
    create_data(root)
    dest = tmp_path / 'weak.hyb'
    with pytest.raises(BackupError, match='12'):
        create_encrypted_backup(root, 'short', dest)
    assert not dest.exists()
