"""Safe, local desktop backup restoration without overwriting live HR records.

Every recovery is a new sibling data profile. An atomic pointer selects it only on
next process start; existing profiles and candidate documents remain untouched.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import uuid
from pathlib import Path

from .backup import BackupError, restore_to_new_directory

_PROFILE = re.compile(r"restored-[0-9a-f]{16}\Z")
_POINTER = 'active-profile.json'
_REQUIRED = {'tasks', 'resumes', 'runs', 'evaluations', 'reviews', 'imports'}


def _valid_name(name: str) -> bool:
    return name == 'data' or bool(_PROFILE.fullmatch(name))


def _path(home: Path, name: str) -> Path:
    if not isinstance(name, str) or not _valid_name(name):
        raise BackupError('本地档案配置无效，请联系管理员')
    candidate = home / name
    # Both the profile and the home directory must not lead outside the app home.
    if candidate.is_symlink() or candidate.resolve() != home.resolve() / name:
        raise BackupError('档案目录包含不安全的路径')
    return candidate


def _load_config(home: Path) -> dict:
    config = home / _POINTER
    if config.is_symlink():
        raise BackupError('本地档案配置不能是符号链接')
    if not config.exists():
        return {'profile': 'data', 'previous': None}
    try:
        raw = json.loads(config.read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or raw.get('version') != 1:
            raise ValueError('invalid')
        name = raw.get('profile')
        previous = raw.get('previous')
        _path(home, name)
        if previous is not None:
            _path(home, previous)
        return {'profile': name, 'previous': previous}
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise BackupError('本地档案配置损坏；为保护原数据，请不要重新初始化') from exc


def active_data_directory(home: Path) -> Path:
    """Resolve once when Windows application starts; never switch mid-session."""
    home = Path(home)
    config = _load_config(home)
    chosen = _path(home, config['profile'])
    if config['profile'] != 'data' and not (chosen / 'huiyan.sqlite3').is_file():
        raise BackupError('恢复档案不存在，已阻止创建空白数据库')
    return chosen


def _write_config(home: Path, profile: str, previous: str | None) -> None:
    _path(home, profile)
    if previous is not None:
        _path(home, previous)
    home.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=home,
                                         prefix='.huiyan-profile-', delete=False) as out:
            temp_path = Path(out.name)
            json.dump({'version': 1, 'profile': profile, 'previous': previous}, out)
            out.flush()
            os.fsync(out.fileno())
        temp_path.replace(home / _POINTER)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _check_restored_schema(root: Path) -> None:
    """Do not activate arbitrary or incomplete SQLite databases from an archive."""
    with sqlite3.connect(f'file:{(root / "huiyan.sqlite3").as_posix()}?mode=ro', uri=True) as db:
        actual = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not _REQUIRED.issubset(actual):
            raise BackupError('备份数据库缺少慧眼所需的数据表，已拒绝激活')
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise BackupError('恢复档案数据库校验失败')


def stage_restore(active_root: Path, archive: Path, password: str) -> dict:
    """Validate a user-selected .hyb archive and activate it on next restart only."""
    active_root = Path(active_root)
    home = active_root.parent
    if not _valid_name(active_root.name):
        raise BackupError('恢复仅支持 Windows 本机慧眼档案目录')
    if not active_root.is_dir() or active_root.is_symlink():
        raise BackupError('找不到当前有效的本地招聘档案')
    # Protect against racing with a previously staged switch in another window.
    cfg = _load_config(home)
    if cfg['profile'] != active_root.name:
        raise BackupError('已有待生效的档案切换，请先关闭并重新打开慧眼')
    new_name = 'restored-' + uuid.uuid4().hex[:16]
    target = _path(home, new_name)
    restore = restore_to_new_directory(archive, password, target)
    try:
        _check_restored_schema(target)
        _write_config(home, new_name, active_root.name)
    except BaseException:
        # Preserve existing active records. Failed restored profiles are disposable.
        import shutil
        shutil.rmtree(target, ignore_errors=True)
        raise
    return {'restored_files': restore['restored_files'], 'restart_required': True,
            'original_preserved': True, 'profile': new_name}


def profile_status(active_root: Path) -> dict:
    root = Path(active_root)
    home = root.parent
    cfg = _load_config(home)
    current = cfg['profile']
    prev = cfg['previous']
    return {'current_profile': root.name, 'pending_profile': current if current != root.name else None,
            'previous_profile': prev if prev and prev != root.name else None,
            'can_return_to_original': root.name != 'data' and (home / 'data' / 'huiyan.sqlite3').is_file()}


def schedule_original_profile(active_root: Path) -> dict:
    """Schedule returning to initial data profile, again with no deletion."""
    root = Path(active_root)
    if root.name == 'data':
        raise BackupError('当前已经使用最初的本地档案')
    home = root.parent
    cfg = _load_config(home)
    if cfg['profile'] != root.name:
        raise BackupError('已有待生效的档案切换，请先重启应用')
    original = _path(home, 'data')
    if not (original / 'huiyan.sqlite3').is_file():
        raise BackupError('最初的招聘档案不存在，无法切回')
    _write_config(home, 'data', root.name)
    return {'restart_required': True, 'original_preserved': True}
