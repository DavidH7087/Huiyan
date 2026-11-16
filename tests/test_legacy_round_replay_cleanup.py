"""Legacy history criteria are cleaned only for a NEW run or settings restoration.

The historic 4 rounds, evaluations and review notes remain immutable.
"""
import json

from fastapi.testclient import TestClient
from backend.app import clean_reused_criteria, create_app


def test_four_original_rounds_survive_and_replay_removes_invalid_hiring_reference(tmp_path):
    with TestClient(create_app(tmp_path / 'history')) as client:
        description=('【功能测试】招聘B2B销售，必须有企业客户开发经验，'
                     '优先考虑制造业、大客户管理和渠道拓展经验。')
        task=client.post('/api/tasks',json={
            'title':'测试B2B销售', 'description':description,
            'required':['B2B销售','客户开发'],
            'preferred':['制造业','大客户管理','渠道拓展'],
            'description_leads':['B2B销售','客户开发','制造业','大客户管理','渠道拓展']
        }).json()
        url=f'/api/tasks/{task["id"]}'
        samples=[
            ('files',('positive.txt',
                     '张三\n独立负责工业品销售、客户开发、制造业大客户管理、渠道拓展。'.encode('utf8'),
                     'text/plain')),
            ('files',('negative.txt','李四\n没有B2B销售与客户开发经验。'.encode('utf8'),'text/plain')),
        ]
        assert client.post(url+'/resumes',files=samples).json()['imported']==2
        rounds=[client.post(url+'/runs',json={'name':f'原始轮次{i+1}'}).json()
                for i in range(4)]
        original_id=rounds[0]['id']
        historical=dict(rounds[0]['criteria'])
        historical.update({
            'required':['B2B销售','招聘','客户开发'],
            'preferred':['制造业','大客户管理','渠道拓展','招聘'],
            'task_preferred':['制造业','大客户管理','渠道拓展'],
            'description_leads':['招聘','制造业','客户开发'],
            'supplementary_leads':[]
        })
        with client.app.state.store.connect() as cn:
            cn.execute('UPDATE runs SET criteria_json=? WHERE id=?',
                       (json.dumps(historical,ensure_ascii=False),original_id))
        historical_before=client.get(url+f'/runs/{original_id}/results').json()
        assert '招聘' in historical_before['run']['criteria']['required']
        assert len(client.get(url+'/runs').json())==4

        replay=client.post(url+f'/runs/{original_id}/replay')
        assert replay.status_code==200,replay.text
        new=replay.json()
        assert new['criteria']['replay_of']==original_id
        assert new['criteria']['removed_legacy_terms']==['招聘']
        assert new['criteria']['required']==['B2B销售','客户开发']
        assert new['criteria']['preferred']==['制造业','大客户管理','渠道拓展']
        assert '招聘' not in new['criteria']['description_leads']
        assert len(client.get(url+'/runs').json())==5
        new_results=client.get(url+f'/runs/{new["id"]}/results').json()
        positive=next(x for x in new_results['results'] if x['filename']=='positive.txt')
        assert positive['evaluation']['matched_count']==5
        assert positive['evaluation']['evidence_coverage']==100
        assert len(positive['evaluation']['checks'])==5

        historical_after=client.get(url+f'/runs/{original_id}/results').json()
        assert historical_after['run']['criteria']==historical_before['run']['criteria']
        assert historical_after['results']==historical_before['results']
        assert len(client.get(url+'/runs').json())==5
        assert client.get(url).json()['required']==['B2B销售','客户开发']

        restored=client.post(url+f'/runs/{original_id}/restore-criteria')
        assert restored.status_code==200,restored.text
        assert restored.json()['removed_legacy_terms']==['招聘']
        assert restored.json()['task']['required']==['B2B销售','客户开发']
        assert restored.json()['task']['preferred']==['制造业','大客户管理','渠道拓展']
        assert '招聘' not in restored.json()['task']['description_leads']


def test_valid_recruiting_skill_remains_in_hr_recruitment_role(tmp_path):
    with TestClient(create_app(tmp_path / 'hr')) as client:
        task=client.post('/api/tasks',json={
            'title':'招聘专员', 'description':'寻找有校园招聘经验、熟悉招聘流程的招聘专员',
            'required':['团队管理'], 'preferred':['招聘'], 'description_leads':['招聘']
        }).json()
        url=f'/api/tasks/{task["id"]}'
        old=client.post(url+'/runs',json={}).json()
        reused=client.post(url+f'/runs/{old["id"]}/replay').json()
        assert '招聘' in reused['criteria']['preferred']
        assert reused['criteria']['removed_legacy_terms']==[]


def test_manual_required_recruitment_is_never_silently_deleted():
    legacy={'required':['招聘','客户开发'],
            'preferred':['招聘','制造业'],
            'description_leads':['招聘'],
            'task_preferred':['招聘','制造业']}
    cleaned=clean_reused_criteria(legacy,'招聘B2B销售，要求客户开发',
                                 active_required=['招聘','客户开发'])
    assert '招聘' in cleaned['required']
    assert cleaned['removed_legacy_terms']==[]
    assert cleaned['preferred']==['制造业']


def test_source_criteria_without_recruitment_verb_keeps_explicit_recruiting_skill():
    legacy={'required':['Java'], 'preferred':['招聘'], 'task_preferred':['招聘'],
            'description_leads':[]}
    cleaned=clean_reused_criteria(legacy,'Java后端开发',active_required=['Java'])
    assert cleaned['preferred']==['招聘']
    assert cleaned['removed_legacy_terms']==[]
