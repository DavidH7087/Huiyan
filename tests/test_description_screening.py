"""Phase 1: description-only and mixed screening must remain reviewable."""
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.engine import description_clues


def test_free_text_clues_are_bounded_and_skip_negative_requirements():
    leads = description_clues(
        '寻找有企业客户开发经验的人选；最好熟悉制造业；不要求润滑油经验。'
    )
    assert '客户开发' in leads
    assert '制造业' in leads
    assert not any('润滑油' in lead for lead in leads)
    assert len(leads) <= 8


def test_description_only_task_screens_without_mandatory_keywords(tmp_path):
    with TestClient(create_app(tmp_path / 'data')) as client:
        task = client.post('/api/tasks', json={
            'title': '客户发展经理',
            'description': '寻找有企业客户开发经验的人选',
            'required': [], 'preferred': [],
        }).json()
        tid = task['id']
        assert client.post(f'/api/tasks/{tid}/resumes', files=[
            ('files', ('a.txt', '张三\n工作经历：负责客户开发与签约。'.encode('utf-8'), 'text/plain')),
            ('files', ('b.txt', '李四\n工作经历：负责零售门店排班。'.encode('utf-8'), 'text/plain')),
        ]).json()['imported'] == 2
        run = client.post(f'/api/tasks/{tid}/runs', json={}).json()
        results = client.get(f'/api/tasks/{tid}/runs/{run["id"]}/results').json()
        assert results['total'] == 2
        assert results['run']['criteria']['required'] == []
        assert '客户开发' in results['run']['criteria']['description_leads']
        matched = next(x for x in results['results'] if x['filename'] == 'a.txt')
        assert matched['evaluation']['matched_count'] >= 1
        # The nonmatching résumé must remain visible, never auto-rejected.
        assert any(x['filename'] == 'b.txt' for x in results['results'])


def test_mixed_mode_retains_explicit_required_and_informs_about_optional_leads(tmp_path):
    with TestClient(create_app(tmp_path / 'data')) as client:
        task = client.post('/api/tasks', json={
            'title': '销售团队',
            'description': '希望熟悉渠道拓展；最好有制造业经验',
            'required': ['客户开发'], 'preferred': [],
        }).json()
        tid = task['id']
        client.post(f'/api/tasks/{tid}/resumes', files=[
            ('files', ('a.txt', '工作经历：负责渠道拓展，但没有客户开发经验。'.encode('utf-8'), 'text/plain')),
        ])
        run = client.post(f'/api/tasks/{tid}/runs', json={}).json()
        result = client.get(f'/api/tasks/{tid}/runs/{run["id"]}/results').json()
        assert result['run']['criteria']['required'] == ['客户开发']
        assert result['run']['criteria']['description_leads']
        assert result['results'][0]['evaluation']['group'] == '需要确认'


def test_followup_does_not_store_full_paragraph_as_exact_keyword(tmp_path):
    with TestClient(create_app(tmp_path / 'data')) as client:
        task = client.post('/api/tasks', json={
            'title': '项目招聘', 'description': '希望熟悉客户开发', 'required': ['客户开发']
        }).json()
        tid = task['id']
        run = client.post(f'/api/tasks/{tid}/runs', json={
            'query': '最好有制造业经验，并且熟悉渠道拓展的候选人'
        }).json()
        assert run['criteria']['supplementary_leads']
        assert '最好有制造业经验，并且熟悉渠道拓展的候选人' not in run['criteria']['preferred']
