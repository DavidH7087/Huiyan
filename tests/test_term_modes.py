"""Per-term exact/alias mode remains usable across rounds and restored tasks."""
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.engine import evaluate


def test_per_term_exact_does_not_expand_synonyms_but_other_terms_do():
    pages=[{'page':1,'source':'txt','text':'负责工业品销售、客户开发和制造企业项目。'}]
    both=evaluate(['B2B销售','客户开发'],[],pages)
    mixed=evaluate(['B2B销售','客户开发'],[],pages,term_modes={'B2B销售':'exact'})
    assert both['required_met_textually']==2
    assert mixed['required_met_textually']==1
    assert mixed['group']=='需要确认'


def test_term_modes_persist_in_db_and_round_rollback(tmp_path):
    with TestClient(create_app(tmp_path/'data')) as client:
        task=client.post('/api/tasks',json={
            'title':'岗位','required':['B2B销售','客户开发'],'term_modes':{'B2B销售':'exact'}
        }).json()
        tid=task['id']
        assert task['term_modes']=={'B2B销售':'exact'}
        client.post(f'/api/tasks/{tid}/resumes',files=[
            ('files',('a.txt','工作经历：工业品销售，客户开发'.encode('utf8'),'text/plain'))
        ])
        first=client.post(f'/api/tasks/{tid}/runs',json={}).json()
        assert first['criteria']['term_modes']=={'B2B销售':'exact'}
        assert client.get(f'/api/tasks/{tid}/runs/{first["id"]}/results').json()['results'][0]['evaluation']['group']=='需要确认'
        client.patch(f'/api/tasks/{tid}',json={'term_modes':{}})
        second=client.post(f'/api/tasks/{tid}/runs',json={}).json()
        assert second['criteria']['term_modes']=={}
        assert client.get(f'/api/tasks/{tid}/runs/{second["id"]}/results').json()['results'][0]['evaluation']['group']=='优先查看'
        restored=client.post(f'/api/tasks/{tid}/runs/{first["id"]}/restore-criteria').json()
        assert restored['task']['term_modes']=={'B2B销售':'exact'}
