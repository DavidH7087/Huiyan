"""Windows desktop entry point: a loopback-only FastAPI server inside WebView2.

The application stores its working database under the user's local app data.
No public network listener, cloud AI service, or external account is required.
"""
from __future__ import annotations

import json
import os
import socket
import secrets
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen


def user_data_dir() -> Path:
    override = os.getenv('HUIYAN_DATA_DIR')
    if override:
        return Path(override).expanduser()
    local = os.getenv('LOCALAPPDATA')
    if not local:
        local = str(Path.home() / 'AppData' / 'Local')
    from backend.restore_profiles import active_data_directory
    return active_data_directory(Path(local) / 'Huiyan')


def run() -> int:
    # PyInstaller --windowed sets stdout/stderr to None. Uvicorn's logger
    # calls isatty() during startup; provide safe sinks before configuring it.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
    directory = user_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['HUIYAN_DATA_DIR'] = str(directory)
    os.environ['HUIYAN_DESKTOP_MODE'] = '1'
    os.environ['HUIYAN_SESSION_TOKEN'] = secrets.token_urlsafe(32)
    # A packaged ONNX model lives next to the AI edition executable.
    if getattr(sys, 'frozen', False) and not os.getenv('HUIYAN_FASTEMBED_CACHE_DIR'):
        bundle = Path(sys.executable).resolve().parent / 'models' / 'fastembed'
        if bundle.is_dir():
            os.environ['HUIYAN_FASTEMBED_CACHE_DIR'] = str(bundle)
    # Binding to 127.0.0.1 (not all interfaces) is mandatory for desktop use.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    os.environ['HUIYAN_SESSION_PORT'] = str(port)
    import uvicorn
    from backend.app import create_app

    backend = create_app(directory)
    server = uvicorn.Server(uvicorn.Config(backend, host='127.0.0.1', port=port, log_level='warning'))
    thread = threading.Thread(target=server.run, name='huiyan-backend', daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            if not thread.is_alive():
                raise RuntimeError('慧眼本地服务启动失败')
            try:
                with urlopen(url + '/api/health', timeout=0.3) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError('慧眼本地服务未能在规定时间内启动')
        if os.getenv('HUIYAN_DESKTOP_SMOKE_REQUIRE_OCR') == '1':
            with urlopen(url + '/api/health', timeout=3) as response:
                ocr_state = json.load(response).get('ocr', {}).get('state')
            if ocr_state != 'ready':
                raise RuntimeError('Windows 便携版 OCR 未就绪：' + str(ocr_state))
        if os.getenv('HUIYAN_DESKTOP_SMOKE_SCAN_PDF') == '1':
            # Synthetic image-only PDF: check the packaged OCR binary can really
            # render and recognise content, rather than only listing languages.
            import io
            from PIL import Image, ImageDraw, ImageFont
            from backend.parsing import extract_pages
            from backend.ocr import LocalOcrService
            picture = Image.new('RGB', (1600, 600), 'white')
            draw = ImageDraw.Draw(picture)
            font_path = Path(os.getenv('WINDIR', 'C:/Windows')) / 'Fonts' / 'arial.ttf'
            if not font_path.is_file():
                raise RuntimeError('OCR smoke test font unavailable')
            font = ImageFont.truetype(str(font_path), 90)
            draw.text((100, 170), 'B2B SALES EXPERIENCE', fill='black', font=font)
            buffer = io.BytesIO()
            picture.save(buffer, format='PDF', resolution=180)
            pages = extract_pages('synthetic-image-only.pdf', buffer.getvalue(), LocalOcrService())
            text = ' '.join(p.get('text', '') for p in pages).upper()
            if not any(p.get('source') == 'ocr' for p in pages) or 'SALES' not in text:
                raise RuntimeError('Windows bundled OCR failed to recognise a synthetic scanned PDF')
        if os.getenv('HUIYAN_DESKTOP_SMOKE_REQUIRE_SEMANTIC') == '1':
            from backend.semantic import LocalSemanticService
            probe = LocalSemanticService()
            matcher = probe.get_matcher()
            if matcher is None:
                raise RuntimeError('AI edition cannot load bundled Chinese ONNX model')
            result = matcher.encoder.encode(['招聘客户开发经历', '长期维护工业制造企业采购关系'])
            if len(result) != 2 or len(result[0]) != 512:
                raise RuntimeError('AI edition returned invalid embedding dimensions')
        # CI verifies the *bundled executable* without opening a GUI.
        if os.getenv('HUIYAN_DESKTOP_SMOKE') == '1':
            return 0
        import webview
        webview.create_window('慧眼 · 智能简历筛选', url + '/?session=' + os.environ['HUIYAN_SESSION_TOKEN'], width=1220, height=790, min_size=(940, 600))
        webview.start(gui='edgechromium')
        return 0
    finally:
        server.should_exit = True
        thread.join(timeout=8)


if __name__ == '__main__':
    try:
        sys.exit(run())
    except Exception as error:
        # Debug tracebacks are allowed ONLY for synthetic, CI-only smoke tests.
        if os.getenv('HUIYAN_DESKTOP_SMOKE') == '1':
            import traceback
            log = os.getenv('HUIYAN_DESKTOP_SMOKE_LOG')
            if log:
                Path(log).write_text(traceback.format_exc(), encoding='utf-8')
        # Never expose resume contents in the normal desktop UI.
        print('慧眼启动失败：' + type(error).__name__ + '。请查看安装说明。', file=sys.stderr)
        sys.exit(1)
