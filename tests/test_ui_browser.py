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
                page.locator('[data-candidate]').first.click()
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
                # Phase 3: exercise the *drop* path rather than file selection only.
                page.locator('#uploadMore').click()
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
                page.get_by_text('此任务已有').wait_for()
                page.locator('#startScreening').click()
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
