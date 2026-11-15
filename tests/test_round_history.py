"""Round comparison/replay and point-in-time review state."""
from fastapi.testclient import TestClient
from backend.app import create_app


def test_history_compare_and_replay_do_not_rewrite_original_rounds(tmp_path):
    with TestClient(create_app(tmp_path/'history')) as c:
        t=c.post('/api/tasks',json={'title':'销售','required':['客户开发'],'preferred':[],'description_leads':[]}).json()
        task=f'/api/tasks/{t["id"]}'
        docs=[
            ('files',('alice.txt','甲\n工作负责客户开发。'.encode('utf8'),'text/plain')),
            ('files',('bob.txt','乙\n从事行政支持工作。'.encode('utf8'),'text/plain'))
        ]
        assert c.post(task+'/resumes',files=docs).json()['imported']==2
        initial=c.post(task+'/runs',json={'name':'第一轮'}).json()
        first_result=c.get(task+f'/runs/{initial["id"]}/results').json()
        assert first_result['total']==2
        a=next(r for r in first_result['results'] if r['filename']=='alice.txt')
        assert a['review_at_run']['status']=='未审核'
        c.patch(task+f'/resumes/{a["resume_id"]}/review',
                json={'status':'加入面试名单','note':'HR 初次核查'})
        second=c.post(task+'/runs',json={'name':'仅面试名单','scope':'parent',
                        'parent_id':initial['id'],'source_filter':'面试名单'}).json()
        second_result=c.get(task+f'/runs/{second["id"]}/results').json()
        assert second_result['total']==1
        assert second_result['results'][0]['review_at_run']['status']=='加入面试名单'
        c.patch(task+f'/resumes/{a["resume_id"]}/review',
                json={'status':'需要补充资料','note':'待补充'})
        old_again=c.get(task+f'/runs/{initial["id"]}/results').json()
        assert next(r for r in old_again['results'] if r['filename']=='alice.txt')['review_at_run']['status']=='未审核'
        assert next(r for r in old_again['results'] if r['filename']=='alice.txt')['review_status']=='需要补充资料'
        compare=c.get(task+'/runs/compare',params={'left':initial['id'],'right':second['id']})
        assert compare.status_code==200,compare.text
        report=compare.json()
        assert report['left']['total']==2 and report['right']['total']==1
        assert report['removed_count']==1 and report['added_count']==0
        replay=c.post(task+f'/runs/{initial["id"]}/replay')
        assert replay.status_code==200,replay.text
        assert replay.json()['candidate_count']==2
        assert replay.json()['criteria']['replay_of']==initial['id']
        assert c.get(task+f'/runs/{initial["id"]}/results').json()['total']==2


def test_comparison_cannot_cross_tasks(tmp_path):
    with TestClient(create_app(tmp_path/'isolated')) as c:
        a=c.post('/api/tasks',json={'title':'职位A'}).json()['id']
        b=c.post('/api/tasks',json={'title':'职位B'}).json()['id']
        ar=c.post(f'/api/tasks/{a}/runs',json={}).json()['id']
        br=c.post(f'/api/tasks/{b}/runs',json={}).json()['id']
        assert c.get(f'/api/tasks/{a}/runs/compare',params={'left':ar,'right':br}).status_code==404
        assert c.post(f'/api/tasks/{a}/runs/{br}/replay').status_code==404
