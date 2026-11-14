"""Windows desktop entry point: a loopback-only FastAPI server inside WebView2.

The application stores its working database under the user's local app data.
No public network listener, cloud AI service, or external account is required.
"""
from __future__ import annotations

import os
import socket
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
    return Path(local) / 'Huiyan' / 'data'


def run() -> int:
    directory = user_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['HUIYAN_DATA_DIR'] = str(directory)
    # Binding to 127.0.0.1 (not all interfaces) is mandatory for desktop use.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
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
        # CI verifies the *bundled executable* without opening a GUI.
        if os.getenv('HUIYAN_DESKTOP_SMOKE') == '1':
            return 0
        import webview
        webview.create_window('慧眼 · 智能简历筛选', url, width=1220, height=790, min_size=(940, 600))
        webview.start(gui='edgechromium')
        return 0
    finally:
        server.should_exit = True
        thread.join(timeout=8)


if __name__ == '__main__':
    try:
        sys.exit(run())
    except Exception as error:
        # Avoid printing private document paths or candidate content to stdout.
        print('慧眼启动失败：' + type(error).__name__ + '。请查看安装说明。', file=sys.stderr)
        sys.exit(1)
