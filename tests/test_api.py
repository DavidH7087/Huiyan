import io
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend.app import create_app


def test_full_flow(tmp_path):
    app=create_app(tmp_path/'appdata')
    with TestClient(app) as c:
        task=c.post('/api/tasks',json={'title':'销售经理','description':'招聘销售','required':['B2B销售','客户开发'],'preferred':['制造业']}).json()
        tid=task['id']
        data='张三\n负责工业品销售，独立开发制造企业客户。'.encode()
        response=c.post(f'/api/tasks/{tid}/resumes',files=[('files',('resume.txt',data,'text/plain'))])
        assert response.status_code==200
        assert response.json()['imported']==1
        again=c.post(f'/api/tasks/{tid}/resumes',files=[('files',('again.txt',data,'text/plain'))]).json()
        assert again['duplicates']==1
        run=c.post(f'/api/tasks/{tid}/runs',json={'name':'第一轮'}).json()
        rid=run['id']
        result=c.get(f'/api/tasks/{tid}/runs/{rid}/results').json()
        assert result['total']==1
        person=result['results'][0]
        assert person['evaluation']['group']=='优先查看'
        assert person['evaluation']['checks'][0]['evidence']['page']==1
        saved=c.patch(f'/api/tasks/{tid}/resumes/{person["resume_id"]}/review',json={'status':'加入面试名单','note':'已人工核实'}).json()
        assert saved['ok']
        new=c.post(f'/api/tasks/{tid}/runs',json={'name':'第二轮','query':'最好熟悉渠道拓展','scope':'parent','parent_id':rid}).json()
        assert new['candidate_count']==1
        assert len(c.get(f'/api/tasks/{tid}/runs').json())==2
        first=c.get(f'/api/tasks/{tid}/runs/{rid}/results').json()
        assert first['results'][0]['review_status']=='加入面试名单'
        response=c.get(f'/api/tasks/{tid}/runs/{rid}/export')
        assert response.status_code==200
        workbook=load_workbook(io.BytesIO(response.content))
        assert workbook.active.max_row==2
        assert c.get('/api/health').json()['offline']


def test_bad_requests_are_isolated(tmp_path):
    app = create_app(tmp_path / 'isolated')
    with TestClient(app) as c:
        t1 = c.post('/api/tasks', json={'title':'销售', 'required':['客户开发']}).json()['id']
        t2 = c.post('/api/tasks', json={'title':'财务'}).json()['id']
        doc = c.post(f'/api/tasks/{t1}/resumes',files=[('files',('candidate.txt','张三\n客户开发'.encode(),'text/plain'))]).json()
        assert doc['imported'] == 1
        row = c.get(f'/api/tasks/{t1}/resumes').json()[0]
        rid = row['id']
        assert c.get(f'/api/tasks/{t2}/resumes/{rid}').status_code == 404
        assert c.patch(f'/api/tasks/{t2}/resumes/{rid}/review',json={'status':'暂不推进'}).status_code == 404
        assert c.post(f'/api/tasks/{t2}/runs',json={'scope':'parent','parent_id':123}).status_code == 404


def test_empty_job_rule_does_not_create_false_priority(tmp_path):
    app = create_app(tmp_path / 'empty')
    with TestClient(app) as c:
        task = c.post('/api/tasks',json={'title':'招聘助理'}).json()
        tid=task['id']
        data='候选人\n有行政管理经验'.encode('utf-8')
        c.post(f'/api/tasks/{tid}/resumes',files=[('files',('candidate.txt',data,'text/plain'))])
        run=c.post(f'/api/tasks/{tid}/runs',json={}).json()
        result=c.get(f'/api/tasks/{tid}/runs/{run["id"]}/results').json()
        assert result['results'][0]['evaluation']['group']=='需要确认'
