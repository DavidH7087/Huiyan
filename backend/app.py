"""Huiyan offline recruitment screening prototype.

The first build uses text evidence retrieval only, not AI-driven hiring decisions.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import re
import uuid
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from openpyxl import Workbook
from .storage import Store
from .local_security import DesktopRequestGuard
from .session_security import DesktopSessionGuard
from .backup import BackupError, MAX_CONTENT, create_encrypted_backup
from .restore_profiles import stage_restore, profile_status, schedule_original_profile
from .duplicates import annotate_possible_duplicates, collect_duplicate_groups
from .engine import split_terms, suggest_conditions, description_clues, evaluate
from .retrieval import bm25_relevance
from .semantic import LocalSemanticService
from .ocr import LocalOcrService
from .profile import PROFILE_VERSION, extract_profile
from starlette.concurrency import run_in_threadpool
from .parsing import ParseError, expand_upload, extract_pages, extract_identity, MAX_ARCHIVE

FRONTEND=Path(__file__).resolve().parents[1]/'frontend'

class TaskCreate(BaseModel):
    title: str=Field(min_length=1,max_length=100)
    description: str=Field(default='',max_length=12000)
    required: list[str]=Field(default_factory=list)
    preferred: list[str]=Field(default_factory=list)
    excluded: list[str]=Field(default_factory=list)
    match_mode: Literal['aliases','exact']='aliases'
    description_leads: list[str]|None=Field(default=None,max_length=8)

class TaskPatch(BaseModel):
    title: str|None=None
    description: str|None=None
    required: list[str]|None=None
    preferred: list[str]|None=None
    excluded: list[str]|None=None
    match_mode: Literal['aliases','exact']|None=None
    description_leads: list[str]|None=Field(default=None,max_length=8)
    archived: bool|None=None

class TaskDelete(BaseModel):
    confirm_title: str=Field(min_length=1,max_length=100)

class ResumeDelete(BaseModel):
    confirm_filename: str=Field(min_length=1,max_length=255)


class BackupPassword(BaseModel):
    password: str = Field(min_length=12, max_length=256)

class DescriptionInput(BaseModel):
    description: str=Field(max_length=12000)

class RunCreate(BaseModel):
    name: str=Field(default='综合筛选',max_length=100)
    query: str=Field(default='',max_length=3000)
    scope: Literal['all','parent']='all'
    parent_id: int|None=None
    source_filter: Literal['全部','优先查看','需要确认','面试名单']='全部'

class ReviewPatch(BaseModel):
    status: Literal['未审核','加入面试名单','需要补充资料','暂不推进']
    note: str=Field(default='',max_length=3000)


def dumps(data):
    return json.dumps(data,ensure_ascii=False)

def row_dict(row):
    return dict(row) if row is not None else None

def get_task(cn,task_id):
    row=cn.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
    if not row:
        raise HTTPException(404,'招聘任务不存在')
    d=row_dict(row)
    d['required']=json.loads(d['required'])
    d['preferred']=json.loads(d['preferred'])
    d['excluded']=json.loads(d['excluded'])
    d['description_leads']=json.loads(d['description_leads']) if d['description_leads'] is not None else None
    d['archived']=bool(d['archived'])
    return d

def get_run(cn,task_id,run_id):
    row=cn.execute('SELECT * FROM runs WHERE id=? AND task_id=?',(run_id,task_id)).fetchone()
    if not row:
        raise HTTPException(404,'筛选轮次不存在')
    return row_dict(row)


def load_resume_profile(cn,resume_id:int,pages:list[dict]) -> dict:
    cached=cn.execute('SELECT extractor_version,profile_json FROM resume_profiles WHERE resume_id=?',
                      (resume_id,)).fetchone()
    if cached and cached['extractor_version']==PROFILE_VERSION:
        return json.loads(cached['profile_json'])
    profile=extract_profile(pages)
    cn.execute('''INSERT INTO resume_profiles(resume_id,extractor_version,profile_json)
        VALUES(?,?,?) ON CONFLICT(resume_id) DO UPDATE SET
        extractor_version=excluded.extractor_version,profile_json=excluded.profile_json,
        updated_at=datetime('now')''',(resume_id,PROFILE_VERSION,dumps(profile)))
    return profile


def create_app(data_dir:Path|None=None):
    root=Path(data_dir or os.environ.get('HUIYAN_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data')))
    store=Store(root)
    semantic=LocalSemanticService()
    ocr=LocalOcrService()
    app=FastAPI(title='慧眼 - 简历筛选助手',version='0.7.2-preview')
    if os.environ.get('HUIYAN_DESKTOP_MODE') == '1':
        if os.environ.get('HUIYAN_SESSION_TOKEN'):
            app.add_middleware(DesktopSessionGuard)
        # Host/Origin validation must run before session bootstrapping.
        app.add_middleware(DesktopRequestGuard)

    @app.get('/api/health')
    def health():
        return {'ok':True,'product':'慧眼','mode':'hybrid_retrieval_v0.2','offline':True,
                'semantic':semantic.status(),'ocr':ocr.status(),
                'backup_available':os.environ.get('HUIYAN_DESKTOP_MODE') == '1',
                'restore_available':os.environ.get('HUIYAN_DESKTOP_MODE') == '1'}

    @app.post('/api/system/backup')
    def export_backup(payload: BackupPassword):
        # Never expose server-side archives through Codespaces public previews.
        if os.environ.get('HUIYAN_DESKTOP_MODE') != '1':
            raise HTTPException(403, '备份下载只在 Windows 本地桌面模式中可用')
        fd, filename = tempfile.mkstemp(prefix='huiyan-encrypted-', suffix='.hyb')
        os.close(fd)
        path = Path(filename)
        try:
            create_encrypted_backup(store.root, payload.password, path)
        except BackupError as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(400, str(exc)) from None
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return FileResponse(path, filename='Huiyan-encrypted-backup.hyb',
                            media_type='application/octet-stream',
                            headers={'Cache-Control': 'no-store'},
                            background=BackgroundTask(lambda: path.unlink(missing_ok=True)))

    @app.get('/api/system/profiles')
    def profiles():
        if os.environ.get('HUIYAN_DESKTOP_MODE') != '1':
            raise HTTPException(403, '档案恢复仅在 Windows 本地桌面模式中可用')
        try:
            return profile_status(store.root)
        except BackupError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post('/api/system/restore')
    async def restore_backup(password: str = Form(...), confirm: str = Form(...),
                             file: UploadFile = File(...)):
        """Restore to a separate local profile; switch after restart only."""
        if os.environ.get('HUIYAN_DESKTOP_MODE') != '1':
            raise HTTPException(403, '档案恢复仅在 Windows 本地桌面模式中可用')
        if confirm != '恢复':
            raise HTTPException(400, '请输入“恢复”确认操作')
        if not 12 <= len(password) <= 256:
            raise HTTPException(400, '备份密码需要 12 至 256 个字符')
        # The upload is an AES-encrypted archive, not a plaintext resume dump.
        # Stream to a bounded temp file so multi-hundred-MB backups do not fill RAM.
        temp = None
        try:
            with tempfile.NamedTemporaryFile(prefix='huiyan-import-', suffix='.hyb',
                                            dir=store.root.parent, delete=False) as out:
                temp = Path(out.name)
                total = 0
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_CONTENT * 2:
                        raise HTTPException(413, '备份超过本版本支持的最大文件大小')
                    out.write(chunk)
            try:
                return await run_in_threadpool(stage_restore, store.root, temp, password)
            except BackupError as exc:
                raise HTTPException(400, str(exc)) from None
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
            await file.close()

    @app.post('/api/system/profile/original')
    def use_original_profile():
        if os.environ.get('HUIYAN_DESKTOP_MODE') != '1':
            raise HTTPException(403, '档案恢复仅在 Windows 本地桌面模式中可用')
        try:
            return schedule_original_profile(store.root)
        except BackupError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post('/api/criteria/suggest')
    def criteria_suggest(payload:DescriptionInput):
        return {**suggest_conditions(payload.description), 'description_leads':description_clues(payload.description)}

    @app.get('/api/tasks')
    def tasks():
        with store.connect() as cn:
            out=[]
            for row in cn.execute('SELECT * FROM tasks ORDER BY archived, id DESC'):
                d=get_task(cn,row['id'])
                d['resume_count']=cn.execute('SELECT COUNT(*) FROM resumes WHERE task_id=?',(row['id'],)).fetchone()[0]
                d['run_count']=cn.execute('SELECT COUNT(*) FROM runs WHERE task_id=?',(row['id'],)).fetchone()[0]
                out.append(d)
            return out

    @app.post('/api/tasks')
    def new_task(payload:TaskCreate):
        with store.connect() as cn:
            c=cn.execute('INSERT INTO tasks(title,description,required,preferred,excluded,match_mode,description_leads) VALUES(?,?,?,?,?,?,?)',
                (payload.title.strip(),payload.description,dumps(split_terms(payload.required)),dumps(split_terms(payload.preferred)),dumps(split_terms(payload.excluded)),payload.match_mode,
                 dumps(split_terms(payload.description_leads)) if payload.description_leads is not None else None))
            return get_task(cn,c.lastrowid)

    @app.get('/api/tasks/{task_id}')
    def task_detail(task_id:int):
        with store.connect() as cn:
            d=get_task(cn,task_id)
            d['resume_count']=cn.execute('SELECT COUNT(*) FROM resumes WHERE task_id=?',(task_id,)).fetchone()[0]
            d['run_count']=cn.execute('SELECT COUNT(*) FROM runs WHERE task_id=?',(task_id,)).fetchone()[0]
            d['import_issues']=[row_dict(r) for r in cn.execute('SELECT * FROM imports WHERE task_id=? AND state != ? ORDER BY id DESC LIMIT 30',(task_id,'成功'))]
            return d

    @app.patch('/api/tasks/{task_id}')
    def patch_task(task_id:int, payload:TaskPatch):
        with store.connect() as cn:
            get_task(cn,task_id)
            edits=payload.model_dump(exclude_unset=True)
            fields=[]; values=[]
            for key,val in edits.items():
                if key in ('required','preferred','excluded') or (key=='description_leads' and val is not None):
                    val=dumps(split_terms(val))
                if key=='archived':
                    val=int(val)
                if key=='title' and not str(val or '').strip():
                    raise HTTPException(400,'岗位名称不能为空')
                fields.append(f'{key}=?'); values.append(val)
            if fields:
                cn.execute(f'UPDATE tasks SET {", ".join(fields)} WHERE id=?',(*values,task_id))
            return get_task(cn,task_id)

    @app.delete('/api/tasks/{task_id}')
    def delete_archived_task(task_id:int, payload:TaskDelete):
        """Irreversibly remove an archived task, all candidates and review history."""
        with store.connect() as cn:
            task=get_task(cn,task_id)
            if not task['archived']:
                raise HTTPException(409,'请先归档任务，再彻底删除')
            if payload.confirm_title != task['title']:
                raise HTTPException(400,'输入的任务名称不一致，已取消删除')
            original_files=[r[0] for r in cn.execute('SELECT stored_file FROM resumes WHERE task_id=?',(task_id,))]
            cn.execute('DELETE FROM evaluations WHERE run_id IN (SELECT id FROM runs WHERE task_id=?)',(task_id,))
            # Child runs must be removed before their parent when foreign keys are on.
            for run in cn.execute('SELECT id FROM runs WHERE task_id=? ORDER BY id DESC',(task_id,)).fetchall():
                cn.execute('DELETE FROM runs WHERE id=?',(run['id'],))
            cn.execute('DELETE FROM resume_profiles WHERE resume_id IN (SELECT id FROM resumes WHERE task_id=?)',(task_id,))
            cn.execute('DELETE FROM reviews WHERE task_id=?',(task_id,))
            cn.execute('DELETE FROM review_events WHERE task_id=?',(task_id,))
            cn.execute('DELETE FROM imports WHERE task_id=?',(task_id,))
            cn.execute('DELETE FROM redaction_events WHERE task_id=?',(task_id,))
            cn.execute('DELETE FROM resumes WHERE task_id=?',(task_id,))
            cn.execute('DELETE FROM tasks WHERE id=?',(task_id,))
        failed=[]
        for filename in original_files:
            # The stored filenames are UUIDs created by this app, never upload paths.
            if not re.fullmatch(r'[0-9a-f]{32}\.(?:pdf|docx|txt)',filename):
                failed.append(filename)
                continue
            try:
                (store.root/'uploads'/filename).unlink(missing_ok=True)
            except OSError:
                failed.append(filename)
        return {'deleted':True,'files':len(original_files),
                'files_pending_cleanup':len(failed),
                'warning':'部分文件清理失败，请联系管理员' if failed else ''}

    @app.delete('/api/tasks/{task_id}/resumes/{resume_id}')
    def delete_resume(task_id: int, resume_id: int, payload: ResumeDelete):
        """Remove one candidate's personal data while leaving the task intact.

        Deletion necessarily removes this candidate's saved evaluations from all
        historical rounds. Previous encrypted backup files remain external and
        must be managed separately under the organisation's retention policy.
        """
        with store.connect() as cn:
            get_task(cn, task_id)
            row = cn.execute(
                'SELECT filename, stored_file FROM resumes WHERE id=? AND task_id=?',
                (resume_id, task_id)).fetchone()
            if row is None:
                raise HTTPException(404, '候选人不存在')
            if payload.confirm_filename != row['filename']:
                raise HTTPException(400, '输入的原文件名称不一致，已取消删除')
            stored_file = row['stored_file']
            cn.execute('DELETE FROM evaluations WHERE resume_id=?', (resume_id,))
            cn.execute('DELETE FROM resume_profiles WHERE resume_id=?', (resume_id,))
            cn.execute('DELETE FROM reviews WHERE resume_id=? AND task_id=?', (resume_id, task_id))
            cn.execute('DELETE FROM review_events WHERE resume_id=? AND task_id=?', (resume_id, task_id))
            cn.execute('DELETE FROM imports WHERE task_id=? AND filename=?', (task_id, row['filename']))
            cn.execute('DELETE FROM resumes WHERE id=? AND task_id=?', (resume_id, task_id))
            # Only a non-identifying deletion count/event remains.
            cn.execute('INSERT INTO redaction_events(task_id, action) VALUES(?,?)',
                       (task_id, 'candidate_delete'))
        pending = False
        if not re.fullmatch(r'[0-9a-f]{32}\.(?:pdf|docx|txt)', stored_file):
            pending = True
        else:
            try:
                (store.root / 'uploads' / stored_file).unlink(missing_ok=True)
            except OSError:
                pending = True
        return {
            'deleted': True, 'files_pending_cleanup': int(pending),
            'history_adjusted': True,
            'warning': ('数据库记录已删除，但原文件清理失败，请联系管理员' if pending else ''),
        }

    @app.get('/api/tasks/{task_id}/review-history')
    def review_history(task_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            return [dict(row) for row in cn.execute(
                """SELECT e.id,e.resume_id,r.name,e.status,e.note,e.occurred_at
                   FROM review_events e LEFT JOIN resumes r ON r.id=e.resume_id AND r.task_id=e.task_id
                   WHERE e.task_id=? ORDER BY e.id DESC LIMIT 500""",(task_id,))]

    @app.post('/api/tasks/{task_id}/resumes')
    async def import_resumes(task_id:int,files:list[UploadFile]=File(...)):
        """Commit each document separately so interrupted batches retain progress."""
        imported=[]; issues=[]; warnings=[]; duplicates=0
        with store.connect() as cn:
            get_task(cn,task_id)
        for upload in files:
            filename=Path((upload.filename or 'unknown').replace('\\','/')).name
            data=await upload.read(MAX_ARCHIVE+1)
            if len(data)>MAX_ARCHIVE:
                issues.append({'filename':filename,'message':'文件超过 100MB'})
                with store.connect() as cn:
                    cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',
                        (task_id,filename,'失败','文件超过 100MB'))
                continue
            try:
                docs=list(expand_upload(filename,data))
            except ParseError as exc:
                issues.append({'filename':filename,'message':str(exc)})
                with store.connect() as cn:
                    cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',
                        (task_id,filename,'失败',str(exc)))
                continue
            for name,content in docs:
                file_hash=hashlib.sha256(content).hexdigest()
                with store.connect() as cn:
                    existing=cn.execute('SELECT id FROM resumes WHERE task_id=? AND content_hash=?',
                                       (task_id,file_hash)).fetchone()
                if existing:
                    duplicates+=1
                    with store.connect() as cn:
                        cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',
                            (task_id,name,'重复','文件内容重复'))
                    continue
                try:
                    pages=await run_in_threadpool(extract_pages,name,content,ocr)
                    person=extract_identity(pages,name)
                except ParseError as exc:
                    issues.append({'filename':name,'message':str(exc)})
                    with store.connect() as cn:
                        cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',
                            (task_id,name,'失败',str(exc)))
                    continue
                stored_file=f'{uuid.uuid4().hex}{Path(name).suffix.lower()}'
                saved_path=store.root/'uploads'/stored_file
                try:
                    saved_path.write_bytes(content)
                    with store.connect() as cn:
                        saved=cn.execute("""INSERT INTO resumes
                            (task_id,filename,content_hash,stored_file,name,phone,email,pages_json)
                            VALUES(?,?,?,?,?,?,?,?)""",
                            (task_id,name,file_hash,stored_file,person['name'],person['phone'],person['email'],dumps(pages)))
                        load_resume_profile(cn,saved.lastrowid,pages)
                        caution=[p for p in pages if p.get('warning')]
                        if caution:
                            count_ocr=sum(p.get('source')=='ocr' for p in caution)
                            notice=f'{len(caution)} 页需要核对，含 {count_ocr} 页 OCR 识别文字'
                        else:
                            notice=''
                        cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',
                            (task_id,name,'需核实' if caution else '成功',notice))
                except Exception:
                    saved_path.unlink(missing_ok=True)
                    raise
                imported.append(name)
                if caution:
                    warnings.append({'filename':name,'message':notice})
        return {'imported':len(imported),'duplicates':duplicates,'issues':issues,
                'warnings':warnings,'ocr_status':ocr.status(),'filenames':imported[:20]}

    @app.get('/api/tasks/{task_id}/imports')
    def list_import_records(task_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            return [dict(row) for row in cn.execute(
                'SELECT id,filename,state,message,created_at FROM imports WHERE task_id=? ORDER BY id DESC LIMIT 300',
                (task_id,))]

    @app.get('/api/tasks/{task_id}/retention')
    def retention_review(task_id:int, days:int=Query(365,ge=30,le=3650)):
        """Preview old personal data; never expire or delete candidates automatically."""
        with store.connect() as cn:
            get_task(cn,task_id)
            cutoff=f'-{days} days'
            total=cn.execute("""SELECT COUNT(*) FROM resumes
                WHERE task_id=? AND imported_at < datetime('now',?)""",
                (task_id,cutoff)).fetchone()[0]
            records=[dict(row) for row in cn.execute("""SELECT id,filename,name,imported_at
                FROM resumes WHERE task_id=? AND imported_at < datetime('now',?)
                ORDER BY imported_at ASC,id ASC LIMIT 100""",(task_id,cutoff))]
            return {'task_id':task_id,'days':days,'due_count':total,'shown':len(records),
                    'candidates':records,'manual_review_required':True,
                    'note':'仅供组织依据合法保留期限审核，系统不会自动删除；外部加密备份需另行管理。'}

    @app.get('/api/tasks/{task_id}/resumes')
    def list_resumes(task_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            return [dict(x) for x in cn.execute('SELECT id,filename,name,phone,email,imported_at FROM resumes WHERE task_id=? ORDER BY id DESC',(task_id,))]

    @app.get('/api/tasks/{task_id}/duplicates')
    def possible_duplicates(task_id: int):
        with store.connect() as cn:
            get_task(cn, task_id)
            rows = [dict(row) for row in cn.execute(
                'SELECT id AS resume_id,name,filename,email,phone FROM resumes WHERE task_id=?', (task_id,))]
        annotate_possible_duplicates(rows)
        groups = collect_duplicate_groups(rows)
        return {'groups':groups,'count':len(groups)}

    @app.get('/api/tasks/{task_id}/resumes/{resume_id}')
    def resume_content(task_id:int,resume_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            row=cn.execute('SELECT * FROM resumes WHERE task_id=? AND id=?',(task_id,resume_id)).fetchone()
            if not row:
                raise HTTPException(404,'简历不存在')
            pages=json.loads(row['pages_json'])
            profile=load_resume_profile(cn,resume_id,pages)
            return {'id':resume_id,'filename':row['filename'],'pages':pages,
                    'name':row['name'],'email':row['email'],'phone':row['phone'],
                    'profile':profile}

    @app.get('/api/tasks/{task_id}/resumes/{resume_id}/profile')
    def resume_profile(task_id:int,resume_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            row=cn.execute('SELECT pages_json FROM resumes WHERE task_id=? AND id=?',(task_id,resume_id)).fetchone()
            if not row:
                raise HTTPException(404,'简历不存在')
            return load_resume_profile(cn,resume_id,json.loads(row['pages_json']))

    @app.get('/api/tasks/{task_id}/resumes/{resume_id}/original')
    def resume_original(task_id:int,resume_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            row=cn.execute('SELECT filename,stored_file FROM resumes WHERE task_id=? AND id=?',(task_id,resume_id)).fetchone()
            if not row:
                raise HTTPException(404,'简历不存在')
            suffix=Path(row['filename']).suffix.lower()
            mime={'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.txt':'text/plain'}.get(suffix,'application/octet-stream')
            path=store.root/'uploads'/row['stored_file']
            return FileResponse(path,media_type=mime,filename=row['filename'],content_disposition_type='inline' if suffix=='.pdf' else 'attachment')

    @app.get('/api/tasks/{task_id}/runs')
    def list_runs(task_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            out=[]
            for row in cn.execute('SELECT * FROM runs WHERE task_id=? ORDER BY id DESC',(task_id,)):
                d=row_dict(row)
                d['criteria']=json.loads(d.pop('criteria_json'))
                d['candidate_count']=cn.execute('SELECT COUNT(*) FROM evaluations WHERE run_id=?',(d['id'],)).fetchone()[0]
                out.append(d)
            return out

    @app.get('/api/tasks/{task_id}/runs/compare')
    def compare_runs(task_id:int, left:int, right:int):
        """Compare immutable evaluation snapshots, not mutable HR review labels."""
        with store.connect() as cn:
            first=get_run(cn,task_id,left)
            second=get_run(cn,task_id,right)
            def collect(run_id):
                result={}
                for row in cn.execute("""SELECT r.id,r.name,r.filename,e.results_json
                    FROM evaluations e JOIN resumes r ON r.id=e.resume_id
                    WHERE r.task_id=? AND e.run_id=?""",(task_id,run_id)):
                    evidence=json.loads(row['results_json'])
                    result[row['id']]={'resume_id':row['id'],'name':row['name'],
                        'filename':row['filename'],'group':evidence['group'],
                        'matched_count':evidence['matched_count']}
                return result
            a=collect(left); b=collect(right)
            def label(row):
                return {key:row[key] for key in ('resume_id','name','filename','group','matched_count')}
            common=set(a)&set(b)
            changed=[{'resume_id':key,'name':a[key]['name'],
                     'before':a[key]['group'],'after':b[key]['group']}
                     for key in sorted(common)
                     if a[key]['group']!=b[key]['group']]
            return {
                'left':{'id':left,'name':first['name'],'criteria':json.loads(first['criteria_json']),
                        'total':len(a)},
                'right':{'id':right,'name':second['name'],'criteria':json.loads(second['criteria_json']),
                         'total':len(b)},
                'same':len(common),
                'added_count':len(set(b)-set(a)),
                'removed_count':len(set(a)-set(b)),
                'changed_group_count':len(changed),
                'added':[label(b[key]) for key in sorted(set(b)-set(a))[:100]],
                'removed':[label(a[key]) for key in sorted(set(a)-set(b))[:100]],
                'changed':changed[:100],
                'note':'仅比较两轮保存的文字证据分组；当前人工审核状态并不属于历史快照。'
            }

    @app.post('/api/tasks/{task_id}/runs')
    def new_run(task_id:int, payload:RunCreate):
        with store.connect() as cn:
            task=get_task(cn,task_id)
            if payload.scope=='parent' and not payload.parent_id:
                raise HTTPException(400,'从当前结果筛选时需要选择上一个轮次')
            if payload.parent_id:
                get_run(cn,task_id,payload.parent_id)
            ids=None
            if payload.source_filter!='全部' and payload.scope!='parent':
                raise HTTPException(400,'只有基于上一轮的筛选才能限定候选人范围')
            if payload.scope=='parent':
                parent_records=cn.execute("""SELECT e.resume_id,e.results_json,rv.status AS review_status
                    FROM evaluations e JOIN resumes r ON r.id=e.resume_id
                    LEFT JOIN reviews rv ON rv.task_id=r.task_id AND rv.resume_id=r.id
                    WHERE e.run_id=? AND r.task_id=?""",(payload.parent_id,task_id)).fetchall()
                ids=[]
                for record in parent_records:
                    if payload.source_filter=='面试名单' and record['review_status']!='加入面试名单':
                        continue
                    if payload.source_filter in ('优先查看','需要确认'):
                        if json.loads(record['results_json'])['group']!=payload.source_filter:
                            continue
                    ids.append(record['resume_id'])
            terms=task['required']+task['preferred']+task['excluded']
            new=suggest_conditions(payload.query)
            additional=[x for x in new['required']+new['preferred']+description_clues(payload.query) if x not in terms]
            # Free-text descriptions are interpreted as bounded, optional evidence leads;
            # never require an exact match on the entire arbitrary paragraph.
            # Added query terms are soft evidence signals, never new hard criteria automatically.
            required=task['required']
            description_leads=(task['description_leads'] if task['description_leads'] is not None
                               else description_clues(task['description']))
            preferred=list(dict.fromkeys(task['preferred']+description_leads+additional))
            excluded=task['excluded']
            match_mode=task['match_mode']
            matcher=semantic.get_matcher()
            criteria={'required':required,'preferred':preferred,'excluded':excluded,'match_mode':match_mode,'query':payload.query,
                      'description_leads':description_leads, 'supplementary_leads':additional,
                      'engine':'hybrid_retrieval_v0.2' if matcher else 'local_evidence_v1',
                      'semantic':semantic.status(), 'source_filter':payload.source_filter,
                      'retrieval':'bm25_lexical_v1'}
            cur=cn.execute('INSERT INTO runs(task_id,parent_id,name,query,scope,criteria_json) VALUES(?,?,?,?,?,?)',
                 (task_id,payload.parent_id,payload.name,payload.query,payload.scope,dumps(criteria)))
            run_id=cur.lastrowid
            if ids is None:
                source=cn.execute('SELECT id,pages_json FROM resumes WHERE task_id=?',(task_id,)).fetchall()
            elif not ids:
                source=[]
            else:
                # Avoid an unbounded IN(?,?,...) and SQLite's variable limit.
                valid_ids=set(ids)
                source=[r for r in cn.execute("""SELECT r.id,r.pages_json FROM resumes r
                     JOIN evaluations e ON e.resume_id=r.id
                     WHERE r.task_id=? AND e.run_id=?""",(task_id,payload.parent_id))
                        if r['id'] in valid_ids]
            # BM25 is a bounded lexical tie-breaker, never a qualification decision.
            parsed=[json.loads(resume['pages_json']) for resume in source]
            corpus=['\n'.join(page.get('text', '') for page in pages)[:12000] for pages in parsed]
            query_text=' '.join([task['description'], *required, *preferred, payload.query])
            relevance=bm25_relevance(query_text, corpus)
            for resume,pages,relevance_score in zip(source,parsed,relevance):
                score=evaluate(required,preferred,pages,semantic_matcher=matcher,excluded=excluded,match_mode=match_mode)
                # Capture the human review state at round creation, independently
                # from the up-to-date review overlay returned to the results UI.
                prior=cn.execute('SELECT status,note FROM reviews WHERE task_id=? AND resume_id=?',
                                 (task_id,resume['id'])).fetchone()
                score['review_at_run']={'status':prior['status'],'note':prior['note']} if prior else {'status':'未审核','note':''}
                score['text_relevance']=relevance_score
                score['sort_key']=round(score['sort_key'] + relevance_score*0.3,5)
                cn.execute('INSERT INTO evaluations(run_id,resume_id,results_json) VALUES(?,?,?)',(run_id,resume['id'],dumps(score)))
            return {'id':run_id,'name':payload.name,'candidate_count':len(source),'criteria':criteria}

    @app.post('/api/tasks/{task_id}/runs/{run_id}/replay')
    def replay_run(task_id:int,run_id:int):
        """Reapply a historical round's criteria against currently stored resumes.

        Does not mutate old snapshots or silently reintroduce erased candidates.
        """
        with store.connect() as cn:
            old=get_run(cn,task_id,run_id)
            original=json.loads(old['criteria_json'])
            required=original.get('required',[])
            preferred=original.get('preferred',[])
            excluded=original.get('excluded',[])
            mode=original.get('match_mode','aliases')
            criteria={**original,'replay_of':run_id,'source_filter':'全部',
                      'replay_scope':'all_current_resumes'}
            name=('复用 · '+old['name'])[:100]
            created=cn.execute("""INSERT INTO runs(task_id,parent_id,name,query,scope,criteria_json)
                VALUES(?,?,?,?,?,?)""",(task_id,run_id,name,old['query'],'all',dumps(criteria)))
            source=cn.execute('SELECT id,pages_json FROM resumes WHERE task_id=?',
                              (task_id,)).fetchall()
            pages=[json.loads(row['pages_json']) for row in source]
            corpus=['\n'.join(p.get('text','') for p in parts)[:12000] for parts in pages]
            scores=bm25_relevance(' '.join([*required,*preferred,old['query']]),corpus)
            matcher=semantic.get_matcher()
            for row,parts,relevance_score in zip(source,pages,scores):
                evaluation=evaluate(required,preferred,parts,semantic_matcher=matcher,
                                    excluded=excluded,match_mode=mode)
                prior=cn.execute('SELECT status,note FROM reviews WHERE task_id=? AND resume_id=?',
                                 (task_id,row['id'])).fetchone()
                evaluation['review_at_run']=({'status':prior['status'],'note':prior['note']}
                                            if prior else {'status':'未审核','note':''})
                evaluation['text_relevance']=relevance_score
                evaluation['sort_key']=round(evaluation['sort_key']+relevance_score*0.3,5)
                cn.execute('INSERT INTO evaluations(run_id,resume_id,results_json) VALUES(?,?,?)',
                           (created.lastrowid,row['id'],dumps(evaluation)))
            return {'id':created.lastrowid,'name':name,
                    'candidate_count':len(source),'criteria':criteria}

    @app.get('/api/tasks/{task_id}/runs/{run_id}/results')
    def results(task_id:int,run_id:int):
        with store.connect() as cn:
            run=get_run(cn,task_id,run_id)
            query='''SELECT r.id AS resume_id,r.name,r.filename,r.phone,r.email,r.pages_json,
                  e.results_json,rv.status AS review_status,rv.note AS review_note
                  FROM evaluations e JOIN resumes r ON r.id=e.resume_id
                  LEFT JOIN reviews rv ON rv.task_id=r.task_id AND rv.resume_id=r.id
                  WHERE e.run_id=? AND r.task_id=?'''
            records=[]
            for row in cn.execute(query,(run_id,task_id)):
                d=dict(row)
                page_records=json.loads(d.pop('pages_json'))
                d['ocr_pages']=sum(p.get('source')=='ocr' for p in page_records)
                d['parse_warnings']=sum(bool(p.get('warning')) for p in page_records)
                d['evaluation']=json.loads(d.pop('results_json'))
                d['review_at_run']=d['evaluation'].get('review_at_run')
                d['review_status']=d['review_status'] or '未审核'
                d['review_note']=d['review_note'] or ''
                records.append(d)
            annotate_possible_duplicates(records)
            records.sort(key=lambda x:(-x['evaluation']['sort_key'],-x['evaluation']['evidence_coverage'],x['resume_id']))
            return {'run':{'id':run_id,'name':run['name'],'query':run['query'],'created_at':run['created_at'],
                           'parent_id':run['parent_id'],'scope':run['scope'],'criteria':json.loads(run['criteria_json'])},
                    'results':records,'total':len(records)}

    @app.patch('/api/tasks/{task_id}/resumes/{resume_id}/review')
    def review(task_id:int,resume_id:int,payload:ReviewPatch):
        with store.connect() as cn:
            get_task(cn,task_id)
            if not cn.execute('SELECT 1 FROM resumes WHERE task_id=? AND id=?',(task_id,resume_id)).fetchone():
                raise HTTPException(404,'简历不存在')
            cn.execute('''INSERT INTO reviews(task_id,resume_id,status,note) VALUES(?,?,?,?)
                ON CONFLICT(task_id,resume_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=datetime('now')''',
                (task_id,resume_id,payload.status,payload.note))
            cn.execute('INSERT INTO review_events(task_id,resume_id,status,note) VALUES(?,?,?,?)',
                (task_id,resume_id,payload.status,payload.note))
            return {'ok':True,'status':payload.status,'note':payload.note}

    @app.get('/api/tasks/{task_id}/runs/{run_id}/export')
    def export_results(task_id:int,run_id:int):
        data=results(task_id,run_id)
        wb=Workbook(); ws=wb.active;ws.title='筛选结果'
        ws.append(['候选人','原文件','电话','邮箱','AI辅助分组','证据覆盖率','匹配条件','待核实条件','人工审核','审核备注','需核对排除线索','关键词匹配模式'])
        def safe(value):
            value=str(value or '')
            return "'"+value if value.startswith(('=','+','-','@')) else value
        for row in data['results']:
            ev=row['evaluation']; checks=ev['checks']
            matched='、'.join(x['term'] for x in checks if x['evidence'])
            unknown='、'.join(x['term'] for x in checks if not x['evidence'])
            ws.append([safe(row['name']),safe(row['filename']),safe(row['phone']),safe(row['email']),ev['group'],
                       ev['evidence_coverage'],safe(matched),safe(unknown),row['review_status'],safe(row['review_note']),
                       safe('、'.join(c['term'] for c in checks if c['kind']=='excluded' and c['evidence'])),
                       '精确文字' if data['run']['criteria'].get('match_mode')=='exact' else '智能同义'])
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for col,width in {'A':20,'B':33,'C':19,'D':30,'E':18,'F':14,'G':48,'H':48,'I':19,'J':38,'K':35,'L':18}.items():
            ws.column_dimensions[col].width=width
        buf=io.BytesIO(); wb.save(buf);buf.seek(0)
        return StreamingResponse(buf,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
           headers={'Content-Disposition':f'attachment; filename="huiyan-task-{task_id}-run-{run_id}.xlsx"'})

    @app.get('/')
    def index():
        return FileResponse(FRONTEND/'index.html')
    app.mount('/assets',StaticFiles(directory=FRONTEND),name='assets')
    app.state.store=store
    return app

app=create_app()
