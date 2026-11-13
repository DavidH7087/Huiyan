"""Lightweight tests of semantic wiring; never download models in CI."""
from backend.semantic import SemanticMatcher, LocalSemanticService, passages
from backend.engine import evaluate
from backend.app import create_app
from fastapi.testclient import TestClient


class FakeEncoder:
    def encode(self, strings, **kwargs):
        result = []
        for text in strings:
            if '企业客户' in text or '工厂采购' in text or '生产企业' in text:
                result.append([1.0, 0.0])
            elif '渠道' in text or '经销商' in text:
                result.append([0.0, 1.0])
            else:
                result.append([-1.0, 0.0])
        return result


class FakeReranker:
    def predict(self, pairs, **kwargs):
        # Choose the manufacturing-purchaser passage among related snippets.
        return [10 if '工厂采购' in excerpt else 0 for _, excerpt in pairs]


def test_semantic_leads_do_not_become_proven_qualifications():
    matcher = SemanticMatcher(FakeEncoder(), FakeReranker())
    pages = [{'page': 2, 'text': '负责面向工厂采购部门介绍工业设备。\n参与生产企业的商务谈判。'}]
    out = evaluate(['企业客户管理'], [], pages, semantic_matcher=matcher)
    assert out['group'] == '需要确认'
    assert out['required_met_textually'] == 0
    check = out['checks'][0]
    assert check['evidence'] is None
    assert check['semantic_hint']['page'] == 2
    assert '工厂采购' in check['semantic_hint']['excerpt']
    assert check['state'] == '语义相关待核实'


def test_no_semantic_when_unrelated_or_no_model():
    matcher = SemanticMatcher(FakeEncoder(), minimum_similarity=0.65)
    out = evaluate(['企业客户管理'], [], [{'page': 1, 'text': '经销商渠道运营与零售工作经历，负责渠道建设'}], matcher)
    assert out['checks'][0]['semantic_hint'] is None
    assert out['checks'][0]['state'] == '待核实'
    assert LocalSemanticService(model_dir='').status()['state'] == 'not_configured'
    broken = LocalSemanticService(model_dir='/nonexistent/offline/model/path')
    assert broken.get_matcher() is None
    assert broken.status()['state'] == 'error'


def test_passage_numbering_and_length_bound():
    pages = [{'page': 7, 'text': '负责' + '工业设备销售' * 120}]
    chunks = passages(pages)
    assert chunks
    assert all(c['page'] == 7 and len(c['excerpt']) <= 360 for c in chunks)
    assert len(chunks) <= 64


def test_free_form_followup_kept_when_not_in_keyword_dictionary(tmp_path):
    app = create_app(tmp_path / 'semantic-api')
    with TestClient(app) as c:
        task = c.post('/api/tasks', json={'title': '项目管理', 'required': ['客户开发']}).json()
        c.post(f'/api/tasks/{task["id"]}/resumes', files=[('files', ('a.txt', '张三\n客户开发经验'.encode(), 'text/plain'))])
        query = '擅长跨部门推动复杂项目落地'
        run = c.post(f'/api/tasks/{task["id"]}/runs', json={'query':query}).json()
        assert query in run['criteria']['preferred']
        assert run['criteria']['engine'] == 'local_evidence_v1'
        assert c.get('/api/health').json()['semantic']['state'] == 'not_configured'


def test_semantic_batch_only_one_encode_call():
    class CountingEncoder(FakeEncoder):
        def __init__(self): self.calls = 0
        def encode(self, sentences, **kwargs):
            self.calls += 1
            return super().encode(sentences, **kwargs)
    encoder = CountingEncoder()
    matcher = SemanticMatcher(encoder)
    result = matcher.search_many(['企业客户开发', '经销商渠道'], [{'page':1,'text':'面向工厂采购部门销售机械设备\n负责渠道伙伴日常协作管理'}])
    assert len(result) == 2
    assert encoder.calls == 1


def test_child_round_uses_selected_candidate_group(tmp_path):
    app = create_app(tmp_path / 'round-scope')
    with TestClient(app) as c:
        task_id = c.post('/api/tasks', json={'title':'销售', 'required':['客户开发']}).json()['id']
        uploaded = c.post(f'/api/tasks/{task_id}/resumes', files=[
            ('files', ('one.txt', '张三\n客户开发，独立联系企业客户'.encode(), 'text/plain')),
            ('files', ('two.txt', '李四\n办公室文职和行政助理工作'.encode(), 'text/plain')),
        ])
        assert uploaded.json()['imported'] == 2
        first = c.post(f'/api/tasks/{task_id}/runs', json={'name':'初次筛选'}).json()
        rid = first['id']
        rows = c.get(f'/api/tasks/{task_id}/runs/{rid}/results').json()['results']
        assert len([r for r in rows if r['evaluation']['group'] == '优先查看']) == 1
        child = c.post(f'/api/tasks/{task_id}/runs', json={
            'name':'从优先人选继续', 'scope':'parent', 'parent_id':rid,
            'source_filter':'优先查看','query':'更关注企业销售体系建设经验'
        })
        assert child.status_code == 200
        assert child.json()['candidate_count'] == 1
        assert child.json()['criteria']['source_filter'] == '优先查看'
        assert c.get(f'/api/tasks/{task_id}/runs/{rid}/results').json()['total'] == 2
        bad = c.post(f'/api/tasks/{task_id}/runs', json={
            'scope':'all', 'source_filter':'面试名单'
        })
        assert bad.status_code == 400


def test_child_round_from_human_review_list(tmp_path):
    app = create_app(tmp_path / 'review-scope')
    with TestClient(app) as c:
        task_id = c.post('/api/tasks', json={'title':'后端工程师','required':['Java']}).json()['id']
        c.post(f'/api/tasks/{task_id}/resumes',files=[('files',('dev.txt','甲\nJava后端开发'.encode(),'text/plain'))])
        rid = c.post(f'/api/tasks/{task_id}/runs',json={}).json()['id']
        candidate = c.get(f'/api/tasks/{task_id}/resumes').json()[0]['id']
        c.patch(f'/api/tasks/{task_id}/resumes/{candidate}/review',json={'status':'加入面试名单','note':'HR 复核后加入'})
        child = c.post(f'/api/tasks/{task_id}/runs',json={
            'scope':'parent','parent_id':rid,'source_filter':'面试名单','query':'项目经验'
        })
        assert child.status_code == 200
        assert child.json()['candidate_count'] == 1
        assert c.get(f'/api/tasks/{task_id}/runs/{rid}/results').json()['results'][0]['review_status']=='加入面试名单'
