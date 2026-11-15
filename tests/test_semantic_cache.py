"""Embedding caching prevents repeated CPU inference across screening rounds."""
from backend.semantic import SemanticMatcher


class CountingEncoder:
    def __init__(self):
        self.calls = []
    def encode(self, texts, **kwargs):
        self.calls.append(list(texts))
        return [[1., 0.] if '客户' in t or '工厂' in t else [0., 1.] for t in texts]


def test_same_candidate_same_round_reuses_vectors():
    encoder=CountingEncoder()
    matcher=SemanticMatcher(encoder=encoder,minimum_similarity=0.2)
    pages=[{'page': 2, 'text': '负责对接工厂采购人员，维护长期客户关系。'}]
    first=matcher.search_many(['企业客户管理'],pages)
    assert first and first['企业客户管理']['page']==2
    assert len(encoder.calls)==1
    same=matcher.search_many(['企业客户管理'],pages)
    assert same==first
    assert len(encoder.calls)==1
    additional=matcher.search_many(['企业客户管理','渠道关系'],pages)
    assert len(encoder.calls)==2
    assert encoder.calls[-1]==['渠道关系']


def test_large_corpus_does_not_grow_cache_unbounded():
    encoder=CountingEncoder()
    matcher=SemanticMatcher(encoder=encoder)
    matcher._cache_limit=4
    for i in range(12):
        matcher.search_many(['客户开发'],[{'page':1,'text':f'第{i}轮客户协调维护项目工作。'}])
        assert len(matcher._cache) <= 4
