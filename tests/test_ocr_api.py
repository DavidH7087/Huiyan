"""Exercise the real HTTP import/results workflow with an injected offline OCR stub."""
import io

from fastapi.testclient import TestClient
from pypdf import PdfWriter

import backend.app as app_module


class FakeLocalOcr:
    def status(self):
        return {'state': 'ready', 'message': '测试用本地 OCR'}

    def recognize_pdf_page(self, content, page_number):
        return '张三\n负责制造企业客户开发，熟悉B2B销售'


def test_scanned_resume_api_provenance_and_review(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, 'LocalOcrService', FakeLocalOcr)
    app = app_module.create_app(tmp_path / 'data')
    doc = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(doc)
    with TestClient(app) as client:
        assert client.get('/api/health').json()['ocr']['state'] == 'ready'
        task = client.post('/api/tasks', json={
            'title': '销售经理', 'required': ['客户开发'], 'preferred': ['B2B销售']
        }).json()
        task_id = task['id']
        upload = client.post(f'/api/tasks/{task_id}/resumes', files=[
            ('files', ('扫描版.pdf', doc.getvalue(), 'application/pdf'))
        ])
        assert upload.status_code == 200
        detail = upload.json()
        assert detail['imported'] == 1
        assert len(detail['warnings']) == 1
        run = client.post(f'/api/tasks/{task_id}/runs', json={'name': '第一轮'}).json()
        rows = client.get(f'/api/tasks/{task_id}/runs/{run["id"]}/results').json()['results']
        assert len(rows) == 1
        assert rows[0]['ocr_pages'] == 1
        assert rows[0]['parse_warnings'] == 1
        assert rows[0]['evaluation']['group'] == '需要确认'
        assert rows[0]['evaluation']['checks'][0]['state'] == 'OCR文字待核实'
        resumes = client.get(f'/api/tasks/{task_id}/resumes').json()
        content = client.get(f'/api/tasks/{task_id}/resumes/{resumes[0]["id"]}').json()
        assert content['pages'][0]['source'] == 'ocr'
        assert client.get(f'/api/tasks/{task_id}').json()['import_issues'][0]['state'] == '需核实'
