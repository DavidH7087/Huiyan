from backend.app import create_app
from fastapi.testclient import TestClient


def test_profile_api_persists_and_migrates_existing_resumes(tmp_path):
    app=create_app(tmp_path/'profiledata')
    with TestClient(app) as c:
        task=c.post('/api/tasks',json={'title':'财务岗','required':['Excel']}).json()['id']
        content='王小明\n教育：本科\n技能 Excel SQL\n3年工作经验\n负责预算核算'.encode()
        res=c.post(f'/api/tasks/{task}/resumes',files=[('files',('one.txt',content,'text/plain'))]).json()
        assert res['imported']==1
        rid=c.get(f'/api/tasks/{task}/resumes').json()[0]['id']
        profile=c.get(f'/api/tasks/{task}/resumes/{rid}/profile').json()
        assert profile['stated_experience_years']==[3]
        assert any(x['label']=='本科' for x in profile['education_mentions'])
        assert any(x['label']=='Excel' for x in profile['skill_mentions'])
        assert c.get(f'/api/tasks/{task}/resumes/{rid}').json()['profile']==profile
        with app.state.store.connect() as db:
            assert db.execute('SELECT COUNT(*) FROM resume_profiles').fetchone()[0]==1
            db.execute('DELETE FROM resume_profiles')
        # Old pre-profile resumes are handled lazily; cross-task access is refused.
        assert c.get(f'/api/tasks/{task}/resumes/{rid}/profile').json()==profile
        other=c.post('/api/tasks',json={'title':'其他'}).json()['id']
        assert c.get(f'/api/tasks/{other}/resumes/{rid}/profile').status_code==404
