"""Task change history and explicit rollback to a stored screening version."""
from fastapi.testclient import TestClient
from backend.app import create_app


def test_restore_previous_task_conditions_preserves_round_results(tmp_path):
    with TestClient(create_app(tmp_path/'data')) as c:
        task=c.post('/api/tasks',json={
            'title':'销售','description':'熟悉渠道拓展',
            'required':['客户开发'],'preferred':['制造业'],'description_leads':['渠道拓展'],
        }).json()
        path=f'/api/tasks/{task["id"]}'
        old=c.post(path+'/runs',json={'name':'招聘初筛'}).json()
        c.patch(path,json={'required':['Java'],'preferred':[], 'description_leads':[]})
        new=c.post(path+'/runs',json={'name':'修改后初筛'}).json()
        assert old['criteria']['required']==['客户开发']
        assert new['criteria']['required']==['Java']
        restore=c.post(path+f'/runs/{old["id"]}/restore-criteria')
        assert restore.status_code==200,restore.text
        restored=restore.json()['task']
        assert restored['required']==['客户开发']
        assert restored['preferred']==['制造业']
        assert restored['description_leads']==['渠道拓展']
        assert restored['description']=='熟悉渠道拓展'
        events=c.get(path+'/changes').json()
        assert len(events)==2
        assert events[0]['action']==f'restore_round:{old["id"]}'
        assert events[1]['action']=='task_edit'
        assert c.get(path+f'/runs/{new["id"]}/results').json()['run']['criteria']['required']==['Java']
        after=c.post(path+'/runs',json={}).json()
        assert after['criteria']['required']==['客户开发']


def test_archived_task_cleanup_erases_task_config_audit_events(tmp_path):
    with TestClient(create_app(tmp_path/'cleanup')) as c:
        task=c.post('/api/tasks',json={'title':'测试'}).json()
        path=f'/api/tasks/{task["id"]}'
        c.patch(path,json={'description':'新描述'})
        assert c.get(path+'/changes').json()
        c.patch(path,json={'archived':True})
        deleted=c.request('DELETE',path,json={'confirm_title':'测试'})
        assert deleted.status_code==200,deleted.text
        assert c.get(path+'/changes').status_code==404
        with c.app.state.store.connect() as cn:
            assert cn.execute('SELECT COUNT(*) FROM task_events').fetchone()[0]==0
