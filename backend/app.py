"""Huiyan offline recruitment screening prototype.

The first build uses text evidence retrieval only, not AI-driven hiring decisions.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from openpyxl import Workbook
from .storage import Store
from .engine import split_terms, suggest_conditions, evaluate
from .semantic import LocalSemanticService
from .parsing import ParseError, expand_upload, extract_pages, extract_identity, MAX_ARCHIVE

FRONTEND=Path(__file__).resolve().parents[1]/'frontend'

class TaskCreate(BaseModel):
    title: str=Field(min_length=1,max_length=100)
    description: str=Field(default='',max_length=12000)
    required: list[str]=Field(default_factory=list)
    preferred: list[str]=Field(default_factory=list)

class TaskPatch(BaseModel):
    title: str|None=None
    description: str|None=None
    required: list[str]|None=None
    preferred: list[str]|None=None
    archived: bool|None=None

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
    d['archived']=bool(d['archived'])
    return d

def get_run(cn,task_id,run_id):
    row=cn.execute('SELECT * FROM runs WHERE id=? AND task_id=?',(run_id,task_id)).fetchone()
    if not row:
        raise HTTPException(404,'筛选轮次不存在')
    return row_dict(row)


def create_app(data_dir:Path|None=None):
    root=Path(data_dir or os.environ.get('HUIYAN_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data')))
    store=Store(root)
    semantic=LocalSemanticService()
    app=FastAPI(title='慧眼 - 简历筛选助手',version='0.2.0')

    @app.get('/api/health')
    def health():
        return {'ok':True,'product':'慧眼','mode':'hybrid_retrieval_v0.2','offline':True,
                'semantic':semantic.status()}

    @app.post('/api/criteria/suggest')
    def criteria_suggest(payload:DescriptionInput):
        return suggest_conditions(payload.description)

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
            c=cn.execute('INSERT INTO tasks(title,description,required,preferred) VALUES(?,?,?,?)',
                (payload.title.strip(),payload.description,dumps(split_terms(payload.required)),dumps(split_terms(payload.preferred))))
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
                if key in ('required','preferred'):
                    val=dumps(split_terms(val))
                if key=='archived':
                    val=int(val)
                if key=='title' and not str(val or '').strip():
                    raise HTTPException(400,'岗位名称不能为空')
                fields.append(f'{key}=?'); values.append(val)
            if fields:
                cn.execute(f'UPDATE tasks SET {", ".join(fields)} WHERE id=?',(*values,task_id))
            return get_task(cn,task_id)

    @app.post('/api/tasks/{task_id}/resumes')
    async def import_resumes(task_id:int,files:list[UploadFile]=File(...)):
        imported=[]; issues=[]; duplicates=0
        with store.connect() as cn:
            get_task(cn,task_id)
            for upload in files:
                filename=Path((upload.filename or 'unknown').replace('\\','/')).name
                data=await upload.read(MAX_ARCHIVE+1)
                if len(data)>MAX_ARCHIVE:
                    issues.append({'filename':filename,'message':'文件超过 100MB'})
                    cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',(task_id,filename,'失败','文件超过 100MB'))
                    continue
                try:
                    docs=list(expand_upload(filename,data))
                except ParseError as exc:
                    issues.append({'filename':filename,'message':str(exc)})
                    cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',(task_id,filename,'失败',str(exc)))
                    continue
                for name,content in docs:
                    file_hash=hashlib.sha256(content).hexdigest()
                    existing=cn.execute('SELECT id FROM resumes WHERE task_id=? AND content_hash=?',(task_id,file_hash)).fetchone()
                    if existing:
                        duplicates+=1
                        cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',(task_id,name,'重复','文件内容重复'))
                        continue
                    try:
                        pages=extract_pages(name,content)
                        person=extract_identity(pages,name)
                    except ParseError as exc:
                        issues.append({'filename':name,'message':str(exc)})
                        cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',(task_id,name,'失败',str(exc)))
                        continue
                    stored_file=f'{uuid.uuid4().hex}{Path(name).suffix.lower()}'
                    (store.root/'uploads'/stored_file).write_bytes(content)
                    cn.execute('INSERT INTO resumes(task_id,filename,content_hash,stored_file,name,phone,email,pages_json) VALUES(?,?,?,?,?,?,?,?)',
                        (task_id,name,file_hash,stored_file,person['name'],person['phone'],person['email'],dumps(pages)))
                    imported.append(name)
                    cn.execute('INSERT INTO imports(task_id,filename,state,message) VALUES(?,?,?,?)',(task_id,name,'成功',''))
        return {'imported':len(imported),'duplicates':duplicates,'issues':issues,'filenames':imported[:20]}

    @app.get('/api/tasks/{task_id}/resumes')
    def list_resumes(task_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            return [dict(x) for x in cn.execute('SELECT id,filename,name,phone,email,imported_at FROM resumes WHERE task_id=? ORDER BY id DESC',(task_id,))]

    @app.get('/api/tasks/{task_id}/resumes/{resume_id}')
    def resume_content(task_id:int,resume_id:int):
        with store.connect() as cn:
            get_task(cn,task_id)
            row=cn.execute('SELECT * FROM resumes WHERE task_id=? AND id=?',(task_id,resume_id)).fetchone()
            if not row:
                raise HTTPException(404,'简历不存在')
            return {'id':resume_id,'filename':row['filename'],'pages':json.loads(row['pages_json']),
                    'name':row['name'],'email':row['email'],'phone':row['phone']}

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
            terms=task['required']+task['preferred']
            new=suggest_conditions(payload.query)
            additional=[x for x in new['required']+new['preferred'] if x not in terms]
            # A free-form follow-up must be searchable even without a term in our
            # small vocabulary. It remains a *soft* criterion awaiting HR review.
            if payload.query.strip() and not additional:
                additional=[payload.query.strip()[:180]]
            # Added query terms are soft evidence signals, never new hard criteria automatically.
            required=task['required']
            preferred=list(dict.fromkeys(task['preferred']+additional))
            matcher=semantic.get_matcher()
            criteria={'required':required,'preferred':preferred,'query':payload.query,
                      'engine':'hybrid_retrieval_v0.2' if matcher else 'local_evidence_v1',
                      'semantic':semantic.status(), 'source_filter':payload.source_filter}
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
            for resume in source:
                score=evaluate(required,preferred,json.loads(resume['pages_json']),semantic_matcher=matcher)
                cn.execute('INSERT INTO evaluations(run_id,resume_id,results_json) VALUES(?,?,?)',(run_id,resume['id'],dumps(score)))
            return {'id':run_id,'name':payload.name,'candidate_count':len(source),'criteria':criteria}

    @app.get('/api/tasks/{task_id}/runs/{run_id}/results')
    def results(task_id:int,run_id:int):
        with store.connect() as cn:
            run=get_run(cn,task_id,run_id)
            query='''SELECT r.id AS resume_id,r.name,r.filename,r.phone,r.email,
                  e.results_json,rv.status AS review_status,rv.note AS review_note
                  FROM evaluations e JOIN resumes r ON r.id=e.resume_id
                  LEFT JOIN reviews rv ON rv.task_id=r.task_id AND rv.resume_id=r.id
                  WHERE e.run_id=? AND r.task_id=?'''
            records=[]
            for row in cn.execute(query,(run_id,task_id)):
                d=dict(row)
                d['evaluation']=json.loads(d.pop('results_json'))
                d['review_status']=d['review_status'] or '未审核'
                d['review_note']=d['review_note'] or ''
                records.append(d)
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
        ws.append(['候选人','原文件','电话','邮箱','AI辅助分组','证据覆盖率','匹配条件','待核实条件','人工审核','审核备注'])
        def safe(value):
            value=str(value or '')
            return "'"+value if value.startswith(('=','+','-','@')) else value
        for row in data['results']:
            ev=row['evaluation']; checks=ev['checks']
            matched='、'.join(x['term'] for x in checks if x['evidence'])
            unknown='、'.join(x['term'] for x in checks if not x['evidence'])
            ws.append([safe(row['name']),safe(row['filename']),safe(row['phone']),safe(row['email']),ev['group'],
                       ev['evidence_coverage'],safe(matched),safe(unknown),row['review_status'],safe(row['review_note'])])
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for col,width in {'A':20,'B':33,'C':19,'D':30,'E':18,'F':14,'G':48,'H':48,'I':19,'J':38}.items():
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
