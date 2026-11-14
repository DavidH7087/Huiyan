"""Local password-encrypted Huiyan backups (experimental desktop feature).

AES-256-GCM authenticates the archive, PBKDF2-HMAC-SHA256 derives a key from a
user-supplied passphrase. Passwords are never written to the archive or logs.
Restore is deliberately restricted to a NEW directory while Huiyan is stopped.
"""
from __future__ import annotations

import getpass
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b'HUIYANBK2\x00'
ITERATIONS = 480_000
MAX_CONTENT = 1024 * 1024 * 1024  # UI backup cap: 1 GiB plaintext
MAX_FILES = 5000
CHUNK = 1024 * 1024
_FILENAME = re.compile(r'^[0-9a-f]{32}\.(?:pdf|docx|txt)$')


class BackupError(ValueError):
    pass


def _key(password: str, salt: bytes) -> bytes:
    if len(password) < 12 or len(password) > 256:
        raise BackupError('备份密码需要 12 至 256 个字符')
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=ITERATIONS).derive(password.encode('utf-8'))


class _EncryptedSink:
    """Non-seekable ZIP destination; encrypts each ZIP chunk immediately."""
    def __init__(self, output, encryptor):
        self.output = output
        self.encryptor = encryptor
        self.position = 0

    def write(self, content):
        self.output.write(self.encryptor.update(content))
        self.position += len(content)
        return len(content)

    def tell(self):
        return self.position

    def flush(self):
        self.output.flush()


def _snapshot_sqlite(database: Path, target: Path):
    with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(target)) as dest:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise BackupError('数据库快照完整性检查失败')


def _zip_file(zf, source: Path, arcname: str):
    h = hashlib.sha256()
    size = 0
    with source.open('rb') as incoming, zf.open(arcname, 'w', force_zip64=True) as outgoing:
        while block := incoming.read(CHUNK):
            outgoing.write(block)
            h.update(block)
            size += len(block)
    return {'sha256': h.hexdigest(), 'bytes': size}


def create_encrypted_backup(root: Path, password: str, destination: Path) -> dict:
    """Write a complete encrypted backup. Caller owns destination cleanup."""
    root = Path(root)
    database = root / 'huiyan.sqlite3'
    if not database.is_file():
        raise BackupError('找不到慧眼本地数据库')
    files = []
    with closing(sqlite3.connect(database)) as conn:
        for (filename,) in conn.execute('SELECT stored_file FROM resumes ORDER BY stored_file'):
            if not _FILENAME.fullmatch(filename):
                raise BackupError('数据库中的原文件名称不符合安全格式')
            path = root / 'uploads' / filename
            if not path.is_file() or path.is_symlink():
                raise BackupError('发现原始简历文件缺失，备份已停止')
            files.append((path, 'uploads/' + filename))
    if len(files) > MAX_FILES:
        raise BackupError('文件数量超出本版备份上限')
    if sum(p.stat().st_size for p, _ in files) + database.stat().st_size > MAX_CONTENT:
        raise BackupError('数据量超过本版 1GB 备份上限')
    # SQLite's online backup API provides a consistent database snapshot. It
    # creates a short-lived plaintext temporary DB; operators should use full-
    # disk encryption where personal data is processed.
    with tempfile.TemporaryDirectory(prefix='huiyan-snapshot-') as workdir:
        snapshot = Path(workdir) / 'huiyan.sqlite3'
        _snapshot_sqlite(database, snapshot)
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = _key(password, salt)
        enc = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        destination = Path(destination)
        try:
            with destination.open('wb') as out:
                out.write(MAGIC + salt + nonce)
                with zipfile.ZipFile(_EncryptedSink(out, enc), 'w', compression=zipfile.ZIP_DEFLATED,
                                     compresslevel=6, allowZip64=True) as zf:
                    manifest = {'format': 'huiyan-backup-v2', 'files': {}}
                    manifest['files']['huiyan.sqlite3'] = _zip_file(zf, snapshot, 'huiyan.sqlite3')
                    for source, arcname in files:
                        manifest['files'][arcname] = _zip_file(zf, source, arcname)
                    zf.writestr('manifest.json', json.dumps(manifest, sort_keys=True))
                out.write(enc.finalize())
                out.write(enc.tag)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return {'documents': len(files), 'encrypted_bytes': destination.stat().st_size}


def _decrypt_to_zip(encrypted: Path, password: str, decrypted: Path):
    encrypted = Path(encrypted)
    length = encrypted.stat().st_size
    header_size = len(MAGIC) + 16 + 12
    if length < header_size + 16 or length > MAX_CONTENT * 2:
        raise BackupError('备份文件大小无效或超出上限')
    with encrypted.open('rb') as src:
        head = src.read(header_size)
        if not head.startswith(MAGIC):
            raise BackupError('不是可识别的慧眼加密备份')
        salt = head[len(MAGIC):len(MAGIC) + 16]
        nonce = head[len(MAGIC) + 16:]
        src.seek(length - 16)
        tag = src.read(16)
        decryptor = Cipher(algorithms.AES(_key(password, salt)), modes.GCM(nonce, tag)).decryptor()
        src.seek(header_size)
        remaining = length - header_size - 16
        try:
            with decrypted.open('wb') as dst:
                while remaining:
                    block = src.read(min(CHUNK, remaining))
                    if not block:
                        raise BackupError('备份内容不完整')
                    remaining -= len(block)
                    dst.write(decryptor.update(block))
                dst.write(decryptor.finalize())  # Verify GCM authentication tag
        except InvalidTag:
            raise BackupError('备份密码错误或文件已被篡改') from None


def restore_to_new_directory(backup_file: Path, password: str, target: Path) -> dict:
    """Verify full authenticated archive before installing to a nonexisting path."""
    target = Path(target)
    if target.exists() or target.is_symlink():
        raise BackupError('恢复目标目录已经存在，禁止覆盖现有招聘数据')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='huiyan-restore-', dir=target.parent) as workdir:
        work = Path(workdir)
        archive = work / 'decrypted.zip'
        _decrypt_to_zip(Path(backup_file), password, archive)
        new_root = work / 'data'
        new_root.mkdir()
        try:
            with zipfile.ZipFile(archive) as zf:
                info = zf.infolist()
                members = {i.filename: i for i in info}
                if len(members) != len(info) or len(info) > MAX_FILES + 2:
                    raise BackupError('备份包含重复或过多文件')
                if 'manifest.json' not in members or 'huiyan.sqlite3' not in members:
                    raise BackupError('备份缺少必要元数据或数据库')
                if members['manifest.json'].file_size > 1024 * 1024:
                    raise BackupError('备份清单过大')
                manifest = json.loads(zf.read('manifest.json'))
                expected = manifest.get('files', {})
                if manifest.get('format') != 'huiyan-backup-v2' or set(members) != set(expected) | {'manifest.json'}:
                    raise BackupError('备份清单与实际文件不一致')
                total = sum(i.file_size for i in info)
                if total > MAX_CONTENT or any(i.file_size > MAX_CONTENT for i in info):
                    raise BackupError('备份包含过大文件')
                for name, meta in expected.items():
                    if name != 'huiyan.sqlite3' and not (name.startswith('uploads/') and _FILENAME.fullmatch(name[8:])):
                        raise BackupError('备份包含不安全的文件路径')
                    file_path = new_root / name
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    h = hashlib.sha256()
                    count = 0
                    with zf.open(name) as src, file_path.open('xb') as dst:
                        while block := src.read(CHUNK):
                            dst.write(block)
                            h.update(block)
                            count += len(block)
                    if h.hexdigest() != meta['sha256'] or count != meta['bytes']:
                        raise BackupError('备份文件校验失败：' + name)
        except (zipfile.BadZipFile, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, BackupError):
                raise
            raise BackupError('备份内容损坏或格式不受支持') from exc
        with closing(sqlite3.connect(new_root / 'huiyan.sqlite3')) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise BackupError('恢复数据库完整性校验失败')
            row_files = {r[0] for r in db.execute('SELECT stored_file FROM resumes')}
            saved_files = ({p.name for p in (new_root / 'uploads').glob('*')}
                           if (new_root / 'uploads').exists() else set())
            if row_files != saved_files:
                raise BackupError('数据库与原始简历文件清单不匹配')
        new_root.rename(target)
        return {'restored_files': len(row_files), 'target': str(target)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='慧眼离线加密备份/恢复工具')
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('source', help='backup: 数据目录；restore: .hyb 加密文件')
    parser.add_argument('destination', help='backup: 输出 .hyb 文件；restore: 全新数据目录')
    args = parser.parse_args()
    password = getpass.getpass('请输入至少 12 个字符的备份密码：')
    if args.action == 'backup':
        result = create_encrypted_backup(Path(args.source), password, Path(args.destination))
    else:
        result = restore_to_new_directory(Path(args.source), password, Path(args.destination))
    print(result)


if __name__ == '__main__':
    main()
