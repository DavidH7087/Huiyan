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
    from backend.semantic import _cosine
    query = '负责企业客户关系维护'
    related = '长期对接工业企业采购主管，维护重点客户合作关系。'
    unrelated = '制作手机游戏UI图标并设计二维角色动画。'
    vectors = matcher.encoder.encode([query, related, unrelated])
    assert all(len(vector) == 512 for vector in vectors)
    score_related = _cosine(vectors[0], vectors[1])
    score_unrelated = _cosine(vectors[0], vectors[2])
    print(f'Chinese BGE score related={score_related:.4f}, unrelated={score_unrelated:.4f}')
    assert score_related > score_unrelated + 0.03
    # Threshold validation is separate from whether actual inference works.
    matcher.minimum_similarity = 0.0
    pages = [{'page':1, 'text': related}]
    out = evaluate([query], [], pages, semantic_matcher=matcher)
    assert out['required_met_textually'] == 0
    hint = out['checks'][0]['semantic_hint']
    assert hint is not None
    assert hint['review_required'] is True
    assert hint['page'] == 1
    assert out['group'] == '需要确认'
