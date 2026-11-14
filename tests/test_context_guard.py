"""Corpus regression: synthetic labels are a test oracle, not hiring ground truth."""
import json
from pathlib import Path

import pytest

from backend.engine import evaluate
from backend.evidence_context import rejection_reason

BASE = Path(__file__).resolve().parents[1] / 'testdata' / 'synthetic'


@pytest.mark.parametrize('text,term', [
    ('应聘方向：Java 后端工程师', 'Java'),
    ('【合成测试简历｜完全虚构｜不得用于真实招聘决策】', '招聘'),
    ('阅读过 Python 入门课程，但没有实际开发经验', 'Python'),
    ('参加过财务核算课程，未实际承担结账工作', '财务核算'),
    ('未曾从事招聘工作，也没有面试经验', '招聘'),
    ('课程大纲涉及 SQL 查询语法', 'SQL'),
    ('负责企业客户的售后协调，未说明是否承担客户开发', '客户开发'),
    ('从未负责库存管理和入库记录', '库存管理'),
])
def test_mention_is_not_qualifying_job_evidence(text, term):
    outcome = evaluate([term], [], [{'page': 1, 'text': text}])
    assert outcome['group'] == '需要确认'
    assert outcome['checks'][0]['evidence'] is None


@pytest.mark.parametrize('text,term', [
    ('工作经历：负责企业客户开发并独立签约', '客户开发'),
    ('过去三年独立负责 Java 服务开发和 SQL 查询', 'Java'),
    ('使用 Python 自动化处理每周报表', 'Python'),
    ('已独立负责仓库库存管理和出入库', '库存管理'),
    ('负责财务核算与月度关账', '财务核算'),
    ('独立负责校园招聘和面试组织', '招聘'),
])
def test_explicit_experience_remains_positive(text, term):
    outcome = evaluate([term], [], [{'page': 2, 'text': text}])
    assert outcome['checks'][0]['evidence'] is not None
    assert outcome['group'] == '优先查看'


def test_positive_history_in_separate_sentence_is_not_erased_by_course():
    result = evaluate(['Java'], [], [{'page': 1, 'text':
        '培训经历：学习 Java 基础。\n工作经历：独立负责 Java Spring Boot 服务开发。'}])
    assert result['checks'][0]['evidence']['excerpt'].startswith('工作经历：')


def test_all_120_synthetic_group_regression():
    jobs = {j['id']: j for j in json.loads((BASE / 'jobs.json').read_text('utf-8'))}
    cases = json.loads((BASE / 'truth.json').read_text('utf-8'))
    mismatch = []
    for case in cases:
        body = (BASE / 'resumes_txt' / case['file']).read_text('utf-8')
        job = jobs[case['job_id']]
        result = evaluate(job['required'], job['preferred'], [{'page': 1, 'text': body}])
        if result['group'] != case['human_expected_group']:
            mismatch.append((case['id'], case['scenario'], result['group']))
    assert len(cases) == 120
    assert not mismatch, mismatch


def test_rejected_mention_has_human_readable_reason():
    assert '求职意向' in rejection_reason('应聘方向：Java 后端工程师', 'Java')
    assert '培训' in rejection_reason('参加过 Python 培训', 'Python')
