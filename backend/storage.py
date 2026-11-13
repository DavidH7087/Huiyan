"""Local SQLite repository; each screening run is an immutable snapshot."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from contextlib import contextmanager

SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', required TEXT NOT NULL DEFAULT '[]', preferred TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL DEFAULT (datetime('now')), archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS resumes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id),
 filename TEXT NOT NULL, content_hash TEXT NOT NULL, stored_file TEXT NOT NULL,
 name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
 pages_json TEXT NOT NULL, imported_at TEXT NOT NULL DEFAULT (datetime('now')),
 UNIQUE(task_id,content_hash)
);
CREATE TABLE IF NOT EXISTS imports (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id),
 filename TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id),
 parent_id INTEGER REFERENCES runs(id), name TEXT NOT NULL,
 query TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT 'all',
 criteria_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS evaluations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES runs(id),
 resume_id INTEGER NOT NULL REFERENCES resumes(id), results_json TEXT NOT NULL,
 UNIQUE(run_id,resume_id)
);
CREATE TABLE IF NOT EXISTS reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL REFERENCES tasks(id),
 resume_id INTEGER NOT NULL REFERENCES resumes(id), status TEXT NOT NULL DEFAULT '未审核',
 note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT (datetime('now')),
 UNIQUE(task_id,resume_id)
);
CREATE TABLE IF NOT EXISTS review_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, resume_id INTEGER NOT NULL,
 status TEXT NOT NULL, note TEXT NOT NULL, occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

class Store:
    def __init__(self,root:Path):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/'uploads').mkdir(exist_ok=True)
        self.db=self.root/'huiyan.sqlite3'
        with self.connect() as cn:
            cn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        cn=sqlite3.connect(self.db)
        cn.row_factory=sqlite3.Row
        cn.execute('PRAGMA foreign_keys=ON')
        try:
            yield cn
            cn.commit()
        except BaseException:
            cn.rollback()
            raise
        finally:
            cn.close()
