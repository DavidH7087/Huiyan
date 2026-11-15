"""Run ONLY in the opt-in model download CI job (not the default test suite)."""
import os
import pytest

from backend.semantic import LocalSemanticService
from backend.engine import evaluate


def test_real_offline_chinese_embeddings_with_fictional_resume():
    if os.getenv('HUIYAN_REAL_FASTEMBED_TEST') != '1':
        pytest.skip('Real FastEmbed model runs only in dedicated integration job')
    assert os.environ.get('HF_HUB_OFFLINE') == '1'
    service = LocalSemanticService()
    matcher = service.get_matcher()
    assert matcher is not None, service.status()
    assert service.status()['state'] == 'ready'
    pages = [{'page':1, 'text':'负责与工厂采购主管对接，协调机械设备采购项目和合同签订。'}]
    out = evaluate(['企业客户管理'], [], pages, semantic_matcher=matcher)
    assert out['required_met_textually'] == 0
    hint = out['checks'][0]['semantic_hint']
    assert hint is not None
    assert hint['review_required'] is True
    assert hint['page'] == 1
    assert out['group'] == '需要确认'
