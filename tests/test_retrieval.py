"""BM25 improves lexical tie ordering without changing HR qualification decisions."""
from backend.retrieval import bm25_relevance, tokens
from backend.engine import evaluate


def test_chinese_and_english_tokens_are_bounded():
    assert '客户' in tokens('负责企业客户开发和渠道建设')
    assert 'java' in tokens('Java Spring Boot Python')
    assert len(tokens('中文客户开发' * 4000, limit=100)) == 100


def test_bm25_relevance_prefers_related_documents():
    docs=['负责企业客户开发，熟悉制造业大客户销售，维护客户关系。',
          '使用 Java 实现分布式服务，解决数据库并发问题。',
          '负责线上招聘面试和社保办理。']
    scores=bm25_relevance('制造业大客户销售，客户开发',docs)
    assert len(scores)==3
    assert scores[0]>scores[1]
    assert scores[0]>scores[2]
    assert all(0<=score<=1 for score in scores)


def test_bm25_has_no_candidate_elimination_logic():
    docs=['客户开发','数据库管理','不熟悉客户开发']
    scores=bm25_relevance('客户开发',docs)
    assert len(scores)==len(docs)
    assert evaluate(['客户开发'], [], [{'page':1,'text':'不熟悉客户开发'}])['group']=='需要确认'


def test_empty_queries_and_zero_docs():
    assert bm25_relevance('客户开发',[])==[]
    assert bm25_relevance('', ['hello','world'])==[0,0]
    assert bm25_relevance('完全无关字段',['Java','Python'])==[0,0]
