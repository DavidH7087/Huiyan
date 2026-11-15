"""Non-destructive local data diagnostics for offline HR installations."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_STORED_NAME=re.compile(r'^[0-9a-f]{32}\.(?:txt|pdf|docx)$')


def inspect_local_data(root: Path) -> dict:
    """Report counts only; never expose, change or copy personal information."""
    root=Path(root)
    database=root/'huiyan.sqlite3'
    if not database.is_file():
        return {'ok':False,'database':'missing','missing_files':0,'orphan_files':0,
                'message':'本地数据库不存在'}
    try:
        with sqlite3.connect(database) as cn:
            integrity=cn.execute('PRAGMA integrity_check').fetchone()[0]
            names={row[0] for row in cn.execute('SELECT stored_file FROM resumes')}
            total=cn.execute('SELECT COUNT(*) FROM resumes').fetchone()[0]
        disk_names={p.name for p in (root/'uploads').iterdir() if p.is_file()} if (root/'uploads').is_dir() else set()
    except (sqlite3.DatabaseError,OSError) as exc:
        return {'ok':False,'database':'unreadable','missing_files':0,'orphan_files':0,
                'message':f'读取数据库或文件失败：{type(exc).__name__}'}
    unsafe=sum(not _STORED_NAME.fullmatch(name) for name in names)
    missing=names-disk_names
    orphan=disk_names-names
    good=integrity=='ok' and not unsafe and not missing and not orphan
    return {'ok':good,'database':'ok' if integrity=='ok' else 'damaged',
            'resume_count':total,'missing_files':len(missing),'orphan_files':len(orphan),
            'unsafe_file_names':unsafe,
            'message':('数据库与本地简历文件一致' if good else '检测到需要人工检查的数据或文件问题')}
