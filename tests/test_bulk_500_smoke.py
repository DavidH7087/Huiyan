"""Bounded synthetic 500-resume ingestion regression, no private resumes.

This is a functional scale smoke, not a real-world DOCX/PDF latency benchmark.
"""
from fastapi.testclient import TestClient
from backend.app import create_app


def test_five_hundred_synthetic_text_resumes_keep_all_candidates_and_history(tmp_path):
    with TestClient(create_app(tmp_path / 'corpus')) as client:
        task=client.post('/api/tasks',json={
            'title':'企业客户开发','required':['客户开发'],'description_leads':[]
        }).json()
        prefix=f'/api/tasks/{task["id"]}'
        for batch in range(0,500,50):
            files=[]
            for index in range(batch,batch+50):
                # Every document has unique non-identifying content.
                body=f'合成候选人 {index:04d}\n工作经历：负责客户开发。客户编号 S{index:04d}。'
                files.append(('files',(f'synthetic-{index:04d}.txt',
                                        body.encode('utf8'),'text/plain')))
            response=client.post(prefix+'/resumes',files=files)
            assert response.status_code==200,response.text
            assert response.json()['imported']==50
        assert len(client.get(prefix+'/resumes').json())==500
        run=client.post(prefix+'/runs',json={})
        assert run.status_code==200,run.text
        assert run.json()['candidate_count']==500
        results=client.get(prefix+f'/runs/{run.json()["id"]}/results').json()
        assert results['total']==500
        assert len({row['resume_id'] for row in results['results']})==500
        assert len(client.get(prefix+'/runs').json())==1
