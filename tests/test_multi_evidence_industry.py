"""Multi-evidence technology experience regression with fictional résumé data.

Do not commit or use a real applicant's résumé as a GitHub test fixture.
"""
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.engine import description_clues, evaluate, find_evidence
from backend.industry_context import industry_evidence, is_technology_experience
from backend.semantic import SemanticMatcher


FICTIONAL_RESUME = """教育背景
2023.9-2027.7 示例大学 计算机科学（本科）
主修课程
计算机网络、数据库、软件工程
实习经历
2025.7-2025.8 上海某工业服务公司（IT实习生）
使用 SQL 和 Tableau 进行产品数据分析，配合研发团队交付。
2026.7-2026.8 深圳某智能驾驶科技公司（无人车产品实习生）
负责无人车产品设计，与厂商对接推动项目落地。
整理开发资料，落实产品合规要求。
项目经历
MicroBit 嵌入式系统项目
负责传感器数据处理与程序调试。
"""


def test_followup_is_atomic_and_tech_work_prioritized():
    assert is_technology_experience('需要科技领域的经验')
    assert description_clues('需要科技领域的经验') == ['科技行业经验']
    pages=[{'page':1,'source':'docx','text':FICTIONAL_RESUME}]
    result=evaluate([],['科技行业经验'],pages)
    check=result['checks'][0]
    assert result['matched_count']==1
    assert result['evidence_coverage']==100
    assert len(check['evidence_matches'])==2
    assert '无人车' in check['evidence_matches'][0]['excerpt']
    assert '深圳某智能驾驶科技公司' in check['evidence']['excerpt']
    assert '上海某工业服务公司' in check['evidence_matches'][1]['excerpt']
    assert all(item['section']=='work' for item in check['evidence_matches'])
    assert any(item['section']=='project' for item in check['background_evidence'])
    assert any(item['section']=='education' for item in check['background_evidence'])


def test_education_and_projects_are_not_claimed_as_industry_employment():
    pages=[{'page':1,'text':"""教育背景
计算机科学本科，学习数据库和 Python
项目经历
MicroBit 嵌入式项目
参与算法和传感器实践
"""}]
    result=evaluate([],['科技行业经验'],pages)
    check=result['checks'][0]
    assert check['evidence'] is None
    assert check['evidence_matches']==[]
    assert result['matched_count']==0
    assert result['group']=='需要确认'
    assert all(item['section']!='work' for item in check['background_evidence'])


def test_generic_matching_collects_multiple_sources_but_counts_once():
    pages=[{'page':2,'text':'工作经历\n负责客户开发。\n管理企业客户开发工作。\n开展客户拜访与客户开发。'}]
    result=evaluate(['客户开发'],[],pages)
    check=result['checks'][0]
    assert len(check['evidence_matches'])==3
    assert len({x['excerpt'] for x in check['evidence_matches']})==3
    assert result['matched_count']==1
    assert result['evidence_coverage']==100
    assert find_evidence('客户开发',pages)==check['evidence']


def test_tech_semantic_never_promotes_course_only_education_to_work():
    class AlwaysRelevantEncoder:
        def encode(self,strings,**kwargs):
            return [[1.0,0.0] for _ in strings]
    matcher=SemanticMatcher(AlwaysRelevantEncoder(),minimum_similarity=0.0)
    pages=[{'page':1,'text':"""教育背景
计算机科学本科
主修课程
学习人工智能和计算机视觉
"""}]
    result=evaluate([],['科技行业经验'],pages,semantic_matcher=matcher)
    check=result['checks'][0]
    assert not check['evidence_matches']
    assert check['semantic_hint'] is None
    assert result['matched_count']==0


def test_api_followup_keeps_existing_round_unchanged(tmp_path):
    with TestClient(create_app(tmp_path/'data')) as client:
        task=client.post('/api/tasks',json={
            'title':'销售','required':['客户开发']
        }).json()
        tid=task['id']
        path=f'/api/tasks/{tid}'
        imported=client.post(path+'/resumes',files=[
            ('files',('synthetic-tech.txt',FICTIONAL_RESUME.encode('utf-8'),'text/plain'))
        ])
        assert imported.json()['imported']==1
        old=client.post(path+'/runs',json={'name':'首次'}).json()
        follow=client.post(path+'/runs',json={'name':'科技领域','scope':'parent',
            'parent_id':old['id'],'query':'需要科技领域的经验'}).json()
        criteria=follow['criteria']
        assert criteria['query']=='需要科技领域的经验'
        assert '科技行业经验' in criteria['preferred']
        results=client.get(path+f'/runs/{follow["id"]}/results').json()
        evaluation=results['results'][0]['evaluation']
        industry=next(x for x in evaluation['checks'] if x['term']=='科技行业经验')
        assert len(industry['evidence_matches'])==2
        assert industry['evidence_matches'][0]['section']=='work'
        assert len(industry['background_evidence'])>=1
        first=client.get(path+f'/runs/{old["id"]}/results').json()
        assert all(c['term']!='科技行业经验'
                   for c in first['results'][0]['evaluation']['checks'])


def test_tech_evidence_query_avoids_empty_or_unrelated_work():
    pages=[{'page':1,'text':"""工作经历
某连锁超市销售店员
负责门店日常销售和盘点工作。
教育背景
大学计算机科学辅修
"""}]
    result=evaluate([],['科技行业经验'],pages)
    assert result['matched_count']==0
    assert result['checks'][0]['evidence_matches']==[]
