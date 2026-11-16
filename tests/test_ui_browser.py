"""Browser E2E smoke: real user clicks against a local FastAPI process.

Uses only synthetic resumes and runs in an isolated temporary data directory.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

playwright = pytest.importorskip('playwright.sync_api')
sync_playwright = playwright.sync_playwright
ROOT = Path(__file__).resolve().parents[1]


def test_basic_hr_workflow_in_chromium(tmp_path):
    with socket.socket() as free:
        free.bind(('127.0.0.1', 0))
        port = free.getsockname()[1]
    env = os.environ.copy()
    env.update({
        'HUIYAN_DATA_DIR': str(tmp_path / 'data'),
        'HUIYAN_OCR_ENABLED': '0',
        'HUIYAN_DESKTOP_MODE': '1',
        'HUIYAN_SESSION_TOKEN': 'synthetic-e2e-launch-session-token',
    })
    server = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1',
         '--port', str(port), '--log-level', 'error'],
        env=env, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if server.poll() is not None:
                pytest.fail('Huiyan server failed to start')
            try:
                with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=0.3) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError):
                time.sleep(0.1)
        else:
            pytest.fail('Huiyan server did not become healthy')

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1360, 'height': 860}, device_scale_factor=1, accept_downloads=True)
            try:
                page.goto(f'http://127.0.0.1:{port}/?session=synthetic-e2e-launch-session-token', wait_until='networkidle')
                assert 'session=' not in page.url
                page.get_by_role('heading', name='开始简历筛选').wait_for()
                page.locator('#newDescription').fill('招聘有企业客户开发经验的 B2B 销售，最好有制造业客户经验。')
                page.locator('#describeNext').click()
                page.locator('#jobTitle').fill('销售经理招聘')
                page.locator('#mustTerms').fill('客户开发')
                page.locator('#bonusTerms').fill('制造业')
                page.locator('#excludedTerms').fill('兼职')
                page.locator('#keywordMode').select_option('exact')
                page.locator('#createTask').click()
                page.locator('#fileInput').set_input_files([
                    {'name': 'candidate.txt', 'mimeType': 'text/plain',
                     'buffer': '张三\n独立开发制造业客户，有企业客户开发经验。'.encode('utf-8')},
                    {'name': 'SYN001_b2b_sales.docx',
                     'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                     'buffer': (ROOT / 'testdata/synthetic/fixtures/SYN001_b2b_sales.docx').read_bytes()},
                    {'name': 'SYN001_b2b_sales.pdf', 'mimeType': 'application/pdf',
                     'buffer': (ROOT / 'testdata/synthetic/fixtures/SYN001_b2b_sales.pdf').read_bytes()},
                ])
                page.locator('#uploadFiles').click()
                page.locator('#startScreening').wait_for(state='visible')
                page.wait_for_function('!document.querySelector("#startScreening").disabled')
                page.locator('#startScreening').click()
                page.locator('.candidate-list').get_by_text('张三').wait_for()
                # Review the actual matching sentence inside the readable résumé.
                page.locator('.candidate-list').get_by_text('张三',exact=True).click()
                page.locator('[data-source-index]').first.click()
                page.get_by_role('heading',name='简历文本').wait_for()
                assert page.locator('#focusedSource[open]').count()==1
                assert page.locator('#focusedSource .resume-text').inner_text()
                assert page.locator('a[href*="/original"]').count()==0
                page.locator('button[data-go="results"]').click()
                page.locator('[data-candidate]').first.click()
                page.locator('[data-preview]').click()
                page.get_by_role('heading',name='工作经验').wait_for()
                page.get_by_role('heading',name='简历文本').wait_for()
                assert page.locator('a[href*="/original"]').count()==0
                assert page.locator('.resume-source').count()>=1
                page.locator('button[data-go="results"]').click()
                page.locator('[data-edit-name]').click()
                page.locator('#candidateNameInput').fill('张小测试')
                page.locator('[data-save-name]').click()
                page.locator('.candidate-list').get_by_text('张小测试').wait_for()
                page.locator('#reviewStatus').select_option('加入面试名单')
                page.locator('#reviewNote').fill('本地自动化测试审核')
                page.locator('[data-save-review]').click()
                page.get_by_text('审核记录已保存').wait_for()
                # Keep a screenshot from the actual rendered HR results page.
                output = ROOT / 'tests' / 'artifacts'
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / 'huiyan-results.png'), full_page=True)
                # Phase 1: HR can edit the automatically extracted soft clues.
                page.locator('#editCriteria').click()
                page.locator('#descClues').fill('制造业')
                page.locator('#createTask').click()
                page.get_by_text('招聘要求已更新', exact=False).wait_for()
                # Phase 2: actual multi-round comparison and reusable conditions.
                page.locator('#followupQuery').fill('最好熟悉渠道拓展')
                page.locator('#screenAgain').click()
                page.locator('[data-run]').nth(1).wait_for()
                page.locator('[data-compare]').nth(1).click()
                page.get_by_role('heading', name='筛选轮次对比').wait_for()
                page.locator('#closeCompare').click()
                page.once('dialog',lambda dialog:dialog.accept())
                page.locator('[data-replay]').nth(1).click()
                page.get_by_text('已按历史条件建立新轮次').wait_for()
                page.once('dialog', lambda dialog:dialog.accept())
                page.locator('[data-restore-criteria]').last.click()
                page.get_by_text('岗位条件已恢复',exact=False).wait_for()
                page.locator('#editCriteria').click()
                assert '客户开发' in page.locator('#mustTerms').input_value()
                page.locator('#createTask').click()
                page.locator('#uploadMore').wait_for(state='visible')
                # Phase 3: exercise the *drop* path rather than file selection only.
                page.locator('#uploadMore').click()
                page.locator('#resumeDropzone').wait_for(state='visible')
                page.evaluate("""() => {
                    const data = new DataTransfer();
                    data.items.add(new File(
                        ['\\u5f20\\u56db\\n\\u72ec\\u7acb\\u8d1f\\u8d23\\u5ba2\\u6237\\u5f00\\u53d1'],
                        'dragged-resume.txt', {type: 'text/plain'}
                    ));
                    const zone = document.getElementById('resumeDropzone');
                    zone.dispatchEvent(new DragEvent('dragover',{bubbles:true,dataTransfer:data}));
                    zone.dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:data}));
                }""")
                page.get_by_text('已选择 1 个文件').wait_for()
                page.locator('#uploadFiles').click()
                # Import is asynchronous: the old '此任务已有' label may still be
                # visible while a new upload is in progress. Wait for the count.
                page.wait_for_function("""() => {
                    const line=document.querySelector('.toolbar')?.innerText||'';
                    return line.includes('4 份简历') &&
                        !document.querySelector('#startScreening')?.disabled;
                }""")
                page.locator('#startScreening').click()
                page.get_by_text('已保存筛选轮次',exact=False).wait_for()
                # Browser download must generate a valid, non-empty Excel file.
                page.locator('#exportExcel').wait_for(state='visible')
                with page.expect_download() as excel_transfer:
                    page.locator('#exportExcel').click()
                excel_download=excel_transfer.value
                assert excel_download.suggested_filename.endswith('.xlsx')
                excel_path=tmp_path/'screening-results.xlsx'
                excel_download.save_as(excel_path)
                from openpyxl import load_workbook
                sheet=load_workbook(excel_path).active
                assert sheet.max_row>=5
                assert '候选人' in str(sheet['A1'].value)
                page.get_by_text('Excel 已交给浏览器下载',exact=False).wait_for()
                page.locator('#openHistory').click()
                page.get_by_text('筛选轮次').first.wait_for()
                assert page.locator('[data-run]').count() >= 1
                page.locator('nav [data-view="archive"]').click()
                page.locator('#backupPassword').wait_for(state='visible')
                page.locator('#backupPassword').fill('a-long-synthetic-test-password')
                with page.expect_download() as transfer:
                    page.locator('#createBackup').click()
                download = transfer.value
                assert download.suggested_filename.endswith('.hyb')
                target = tmp_path / 'ui-export.hyb'
                download.save_as(target)
                assert target.read_bytes().startswith(b'HUIYANBK2\x00')
                page.locator('#restoreFile').set_input_files(target)
                page.locator('#restorePassword').fill('a-long-synthetic-test-password')
                page.locator('#restoreConfirm').fill('恢复')
                page.locator('#restoreBackup').click()
                page.get_by_text('已验证 4 份原始简历',exact=False).wait_for(timeout=45000)
                assert (tmp_path / 'data' / 'huiyan.sqlite3').exists()
                assert len(list(tmp_path.glob('restored-*'))) == 1
                page.screenshot(path=str(output / 'huiyan-recovery.png'),full_page=True)
            finally:
                browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)



def test_technology_experience_groups_multiple_sources_in_chromium(tmp_path):
    """Industry work must appear ahead of projects and education in a real UI."""
    from fastapi.testclient import TestClient
    from backend.app import create_app

    data=tmp_path/'industry-ui-data'
    with TestClient(create_app(data)) as client:
        task=client.post('/api/tasks',json={
            'title':'科技领域复核','preferred':['科技行业经验']
        }).json()
        prefix=f'/api/tasks/{task["id"]}'
        document="""教育背景
2023-2027 某大学计算机科学本科
主修课程
软件工程、数据库
实习经历
2025.7 某工业企业 IT实习生
使用 SQL 参与产品数据分析和优化。
2026.7 深圳某智能驾驶科技公司 无人车产品实习生
负责无人车产品设计，推动厂商项目落地。
项目经历
MicroBit 嵌入式系统项目
参与传感器与程序调试。
"""
        response=client.post(prefix+'/resumes',files=[
            ('files',('fictional-industry.txt',document.encode('utf-8'),'text/plain'))
        ])
        assert response.json()['imported']==1
        created=client.post(prefix+'/runs',json={'name':'行业工作经验'}).json()
        assert created['candidate_count']==1

    with socket.socket() as free:
        free.bind(('127.0.0.1',0))
        port=free.getsockname()[1]
    env=os.environ.copy()
    env.update({
        'HUIYAN_DATA_DIR':str(data),
        'HUIYAN_OCR_ENABLED':'0',
        'HUIYAN_DESKTOP_MODE':'1',
        'HUIYAN_SESSION_TOKEN':'fictional-industry-session-token'
    })
    server=subprocess.Popen(
        [sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1',
         '--port',str(port),'--log-level','error'],
        env=env,cwd=str(ROOT),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL
    )
    try:
        for _ in range(100):
            if server.poll() is not None:
                pytest.fail('Industry UI server failed to start')
            try:
                with urlopen(f'http://127.0.0.1:{port}/api/health',timeout=0.3) as response:
                    if response.status==200:break
            except (URLError,TimeoutError):
                time.sleep(0.1)
        else:
            pytest.fail('Industry UI server did not become healthy')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1360,'height':900})
            try:
                page.goto(f'http://127.0.0.1:{port}/?session=fictional-industry-session-token',
                          wait_until='networkidle')
                page.locator('nav [data-view="tasks"]').click()
                page.locator(f'[data-task="{task["id"]}"]').click()
                page.locator('.candidate-row').first.click()
                item=page.locator('.evidence-item').filter(has_text='科技行业经验')
                item.get_by_text('行业工作经历').wait_for()
                assert item.locator('[data-source-kind="text"]').count()==2
                assert item.locator('[data-source-kind="project"]').count()==1
                assert item.locator('[data-source-kind="education"]').count()==1
                snippets=item.locator('.evidence-group .proof-excerpt').all_inner_texts()
                assert '无人车' in snippets[0]
                assert 'IT实习生' in snippets[1]
                item.locator('[data-source-kind="text"]').nth(1).click()
                page.get_by_role('heading',name='简历文本').wait_for()
                assert page.locator('#focusedSource[open]').count()==1
                assert page.locator('#sourceMatch').count()==1
                assert 'IT' in page.locator('#sourceMatch').inner_text()
            finally:
                browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
