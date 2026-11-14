import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
import backend.app as app_module


def test_partial_batch_is_saved_before_unexpected_error(tmp_path,monkeypatch):
    app=create_app(tmp_path/'data')
    original=app_module.extract_pages
    calls=0
    def failing_second(name,content,ocr):
        nonlocal calls
        calls+=1
        if calls==2:
            raise RuntimeError('unexpected worker failure')
        return original(name,content,ocr)
    monkeypatch.setattr(app_module,'extract_pages',failing_second)
    with TestClient(app) as c:
        tid=c.post('/api/tasks',json={'title':'行政招聘'}).json()['id']
        files=[('files',('a.txt','张三\n行政助理'.encode(),'text/plain')),
               ('files',('b.txt','李四\n行政助理'.encode(),'text/plain'))]
        with pytest.raises(RuntimeError):
            c.post(f'/api/tasks/{tid}/resumes',files=files)
        saved=c.get(f'/api/tasks/{tid}/resumes').json()
        assert len(saved)==1
        imports=c.get(f'/api/tasks/{tid}/imports').json()
        assert len(imports)==1 and imports[0]['state']=='成功'
        monkeypatch.setattr(app_module,'extract_pages',original)
        result=c.post(f'/api/tasks/{tid}/resumes',files=files).json()
        assert result['imported']==1 and result['duplicates']==1
        assert len(c.get(f'/api/tasks/{tid}/resumes').json())==2
