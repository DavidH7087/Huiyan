"""Real XLSX disk-save regression for the native pywebview bridge."""
import io
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from openpyxl import Workbook, load_workbook

from backend.desktop_export import ExportError, save_excel_file
from desktop import DesktopBridge


def workbook_data():
    workbook=Workbook()
    workbook.active.append(['候选人', '审核'])
    workbook.active.append(['合成候选人', '需要确认'])
    data=io.BytesIO()
    workbook.save(data)
    return data.getvalue()


def test_native_excel_export_writes_valid_workbook_after_session_handshake(tmp_path):
    content=workbook_data()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            url=urlsplit(self.path)
            if url.path == '/' and parse_qs(url.query).get('session') == ['test-token']:
                self.send_response(303)
                self.send_header('Set-Cookie', 'huiyan_local_session_1234=test-token; HttpOnly; Path=/')
                self.send_header('Location', '/')
                self.end_headers()
                return
            if url.path == '/':
                self.send_response(200)
                self.end_headers()
                return
            if url.path == '/api/tasks/1/runs/2/export':
                if 'huiyan_local_session_1234=test-token' not in self.headers.get('Cookie', ''):
                    self.send_response(401)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self.send_response(404)
            self.end_headers()

    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        path=tmp_path/'Huiyan-task-1-round-2.xlsx'
        outcome=save_excel_file(f'http://127.0.0.1:{server.server_port}', 'test-token',1,2,path)
        assert outcome['ok'] and outcome['bytes'] == len(content)
        assert path.is_file()
        assert load_workbook(path).active['A2'].value == '合成候选人'
        with pytest.raises(ExportError):
            save_excel_file('http://127.0.0.1:1','test-token',0,2,tmp_path/'bad.xlsx')
        assert not (tmp_path/'bad.xlsx').exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_webview_bridge_dialog_cancel_and_confirmed_disk_save(tmp_path):
    class FakeWindow:
        def __init__(self, value):
            self.value=value
            self.calls=[]
        def create_file_dialog(self, dialog_type, **kwargs):
            self.calls.append((dialog_type,kwargs))
            return self.value

    fake_webview=SimpleNamespace(FileDialog=SimpleNamespace(SAVE=30))
    bridge=DesktopBridge('http://127.0.0.1:1234','test-token')
    cancel=FakeWindow(None)
    bridge.attach_window(cancel)
    with patch.dict(sys.modules, {'webview':fake_webview}):
        assert bridge.export_excel(1,2)['cancelled'] is True
        destination=tmp_path/'test.xlsx'
        accepted=FakeWindow((str(destination),))
        bridge.attach_window(accepted)
        with patch('backend.desktop_export.save_excel_file',
                   return_value={'ok':True,'filename':'test.xlsx','bytes':123}) as save:
            response=bridge.export_excel(1,2)
        assert response['ok'] is True
        assert accepted.calls[0][1]['save_filename'].endswith('.xlsx')
        assert save.call_args.args[-1] == str(destination)
