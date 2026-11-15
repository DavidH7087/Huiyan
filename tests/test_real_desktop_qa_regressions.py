"""Regressions taken from the 2026-11-15 real Windows desktop QA report.

Everything here is synthetic; no applicant information is retained.
"""
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.engine import (
    description_clues, dedupe_conditions, expand_description_leads, evaluate, suggest_conditions,
)
from backend.profile import extract_profile, PROFILE_VERSION
from backend.semantic import SemanticMatcher


class UncriticalEncoder:
    """Models the dangerous situation where everything scores as similar."""
    def encode(self, strings, **kwargs):
        return [[1.0, 0.0] for _ in strings]


def test_hiring_word_not_mistaken_for_recruitment_skill():
    jd = ('【功能测试】招聘B2B销售，必须有企业客户开发经验，'
          '优先考虑制造业、大客户管理和渠道拓展经验。')
    suggested = suggest_conditions(jd)
    assert '招聘' not in suggested['required']
    assert suggested['required'] == ['B2B销售', '客户开发']
    assert set(suggested['preferred']) == {'制造业', '大客户管理', '渠道拓展'}
    clues = description_clues(jd)
    assert set(clues) == {'B2B销售', '客户开发', '制造业', '大客户管理', '渠道拓展'}
    assert not any('必须有' in item or '考虑' in item for item in clues)


def test_recruitment_is_a_real_skill_when_job_is_hr_recruiter():
    assert '招聘' in suggest_conditions('寻找有校园招聘经验的招聘专员')['required']
    assert '招聘' not in suggest_conditions('招聘销售经理，要求具备客户开发能力')['required']


def test_semantic_negative_never_shown_as_positive_experience():
    matcher = SemanticMatcher(UncriticalEncoder(), minimum_similarity=0.0)
    text = '没有B2B销售经验，也没有客户开发经验'
    out = evaluate(['B2B销售', '客户开发'], [], [
        {'page': 1, 'source': 'txt', 'text': text}
    ], semantic_matcher=matcher)
    assert out['group'] == '需要确认'
    assert out['matched_count'] == 0
    assert out['semantic_hint_count'] == 0
    assert all(c['semantic_hint'] is None for c in out['checks'])
    assert all(c['negative_evidence']['excerpt'] == text for c in out['checks'])


def test_semantic_python_backend_does_not_imply_customer_development():
    matcher = SemanticMatcher(UncriticalEncoder(), minimum_similarity=0.0)
    out = evaluate(['客户开发'], [], [
        {'page': 1, 'source': 'txt',
         'text': '工作经历：Python后端开发，SQL数据库维护，自动化测试'}
    ], semantic_matcher=matcher)
    assert out['group'] == '需要确认'
    assert out['matched_count'] == 0
    assert out['semantic_hint_count'] == 0
    assert out['checks'][0]['state'] == '待核实'


def test_distinct_textual_skills_count_once_even_with_legacy_clues():
    required=['B2B销售', '客户开发']
    preferred=['B2B销售', '必须有企业客户开发', '考虑制造业',
               '大客户管理', '渠道拓展经验', '客户开发']
    clean_required, clean_preferred = dedupe_conditions(required, preferred)
    assert clean_required == required
    assert len(clean_preferred) == 3
    # The API cleans legacy auto-generated hints before evaluating a new round.
    out = evaluate(required, expand_description_leads(preferred), [{
        'page':1,'source':'txt',
        'text':'独立负责B2B销售、客户开发、制造业、大客户管理和渠道拓展。'
    }])
    assert len(out['checks']) == 5
    assert out['matched_count'] == 5


def test_skills_years_are_distinguished_from_total_work_years():
    profile=extract_profile([{'page':1,'source':'txt',
                             'text':'工作经历：5年B2B销售与企业客户开发经验'}])
    assert PROFILE_VERSION == 'rules-v2'
    assert profile['stated_experience_years'] == [5]
    assert any(item['years']==5 and item['scope']=='specific'
               for item in profile['experience_duration_mentions'])
    total=extract_profile([{'page':1,'text':'5年工作经验'}])
    assert any(item['scope']=='total' for item in total['experience_duration_mentions'])
    assert not extract_profile([{'page':1,'text':'2020-2025年销售管理'}])['stated_experience_years']


def test_desktop_qa_end_to_end_unique_conditions_and_snapshot(tmp_path):
    with TestClient(create_app(tmp_path/'qa')) as client:
        jd=('【功能测试】招聘B2B销售，必须有企业客户开发经验，'
            '优先考虑制造业、大客户管理和渠道拓展经验。')
        task=client.post('/api/tasks',json={
            'title':'功能测试-B2B销售-1115', 'description':jd,
            'required':['B2B销售','客户开发'],
            'preferred': ['制造业', '大客户管理', '渠道拓展'],
            'description_leads':['B2B销售','必须有企业客户开发',
                                 '考虑制造业','大客户管理','渠道拓展'],
        }).json()
        tid=task['id']
        samples={
            'positive.txt':'张三\n工作经历：5年B2B销售与企业客户开发经验，独立负责制造业大客户管理和渠道拓展。',
            'negative.txt':'李四\n没有B2B销售经验，也没有客户开发经验。',
            'unrelated.txt':'王五\n工作经历：Python后端开发，SQL数据库维护，自动化测试。',
        }
        for name,body in samples.items():
            response=client.post(f'/api/tasks/{tid}/resumes',files=[
                ('files',(name,body.encode('utf-8'),'text/plain'))
            ])
            assert response.json()['imported']==1
        run=client.post(f'/api/tasks/{tid}/runs',json={}).json()
        assert len(run['criteria']['preferred']) == 3
        results=client.get(f'/api/tasks/{tid}/runs/{run["id"]}/results').json()
        by_name={x['filename']:x['evaluation'] for x in results['results']}
        assert len(by_name['positive.txt']['checks'])==5
        assert by_name['positive.txt']['matched_count']==5
        assert by_name['negative.txt']['group']=='需要确认'
        assert by_name['unrelated.txt']['group']=='需要确认'
        original=client.get(f'/api/tasks/{tid}/resumes/{next(x["resume_id"] for x in results["results"] if x["filename"]=="positive.txt")}').json()
        assert 5 in original['profile']['stated_experience_years']
