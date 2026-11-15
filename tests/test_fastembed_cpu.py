"""Offline-first fastembed adapter tests. No network or model download in regular CI."""
from __future__ import annotations

import sys
import types

from backend.fastembed_cpu import FastEmbedEncoder, MODEL_NAME
from backend.semantic import LocalSemanticService
from backend.engine import evaluate


class FakeEmbeddingModel:
    calls = []
    def __init__(self, **kwargs):
        self.calls.append(('init', kwargs))
    def embed(self, values, **kwargs):
        self.calls.append(('embed', list(values), kwargs))
        for line in values:
            yield [1.0, 0.0] if '企业' in line or '工厂' in line else [0.0, 1.0]


def test_fastembed_loader_is_offline_and_compatible(tmp_path, monkeypatch):
    FakeEmbeddingModel.calls.clear()
    monkeypatch.setitem(sys.modules, 'fastembed', types.SimpleNamespace(TextEmbedding=FakeEmbeddingModel))
    encoder = FastEmbedEncoder(tmp_path)
    assert encoder.encode(['企业客户管理', '工厂采购合同']) == [[1.0,0.0],[1.0,0.0]]
    assert FakeEmbeddingModel.calls[0][1]['model_name'] == MODEL_NAME
    assert FakeEmbeddingModel.calls[0][1]['local_files_only'] is True
    assert FakeEmbeddingModel.calls[0][1]['threads'] == 2
    matcher = LocalSemanticService(fastembed_cache_dir=str(tmp_path)).get_matcher()
    assert matcher is not None
    pages = [{'page': 3, 'text': '通过走访工厂采购经理推进工业设备采购合同。'}]
    result = evaluate(['企业客户管理'], [], pages, semantic_matcher=matcher)
    assert result['group'] == '需要确认'
    assert result['checks'][0]['state'] == '语义相关待核实'
    assert result['checks'][0]['semantic_hint']['page'] == 3


def test_absent_fastembed_does_not_break_screening(tmp_path):
    not_installed = tmp_path / 'missing-model'
    service = LocalSemanticService(fastembed_cache_dir=str(not_installed))
    assert service.get_matcher() is None
    assert service.status()['state'] == 'error'
    result = evaluate(['渠道拓展'], [], [{'page':1,'text':'负责客户服务'}], semantic_matcher=service.get_matcher())
    assert result['group'] == '需要确认'


def test_explicit_download_flag_is_opt_in(tmp_path, monkeypatch):
    FakeEmbeddingModel.calls.clear()
    monkeypatch.setitem(sys.modules, 'fastembed', types.SimpleNamespace(TextEmbedding=FakeEmbeddingModel))
    FastEmbedEncoder(tmp_path / 'prepare-me', allow_download=True)
    assert FakeEmbeddingModel.calls[0][1]['local_files_only'] is False
