"""Upgrade regression: opening old local recruitment data must preserve records."""
import json
import sqlite3

from backend.storage import Store


def test_legacy_database_is_migrated_without_losing_hr_records(tmp_path):
    root = tmp_path / 'data'
    root.mkdir()
    database = root / 'huiyan.sqlite3'
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                required TEXT NOT NULL DEFAULT '[]',
                preferred TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT '2026-10-01 10:00:00',
                archived INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE resumes (
                id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL,
                filename TEXT NOT NULL, content_hash TEXT NOT NULL,
                stored_file TEXT NOT NULL, name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
                pages_json TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT '2026-10-01 10:00:00',
                UNIQUE(task_id,content_hash)
            );
        """)
        db.execute("INSERT INTO tasks (id,title,required,preferred) VALUES (7,'老版本招聘档案','[\"客户开发\"]','[]')")
        db.execute("""INSERT INTO resumes
                   (id,task_id,filename,content_hash,stored_file,name,pages_json)
                   VALUES (8,7,'candidate.txt','example-hash','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.txt',
                           '虚构候选人','[{"page":1,"text":"企业客户开发","source":"txt"}]')""")
    (root / 'uploads').mkdir(exist_ok=True)
    (root / 'uploads' / ('a' * 32 + '.txt')).write_text('虚构候选人：企业客户开发',encoding='utf-8')

    Store(root)  # Apply supported forward-only schema migrations.
    with sqlite3.connect(database) as db:
        columns = {row[1] for row in db.execute('PRAGMA table_info(tasks)')}
        assert {'excluded', 'match_mode'} <= columns
        row = db.execute('SELECT title,required,excluded,match_mode FROM tasks WHERE id=7').fetchone()
        assert row == ('老版本招聘档案', '["客户开发"]', '[]', 'aliases')
        candidate = db.execute('SELECT name,pages_json FROM resumes WHERE id=8').fetchone()
        assert candidate[0] == '虚构候选人'
        assert json.loads(candidate[1])[0]['text'] == '企业客户开发'
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

    Store(root)  # Re-opening an already upgraded profile must also be safe.
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM resumes').fetchone()[0] == 1
