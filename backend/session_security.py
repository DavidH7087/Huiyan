"""Per-launch cookie-bound access for the Windows loopback HR data service.

The secret is generated when the desktop process starts and passed ONLY to the
local WebView2 startup URL. No account sign-in or cloud authentication needed.
"""
from __future__ import annotations

import hmac
import os
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

COOKIE = 'huiyan_local_session'


def _cookie_name() -> str:
    suffix = os.environ.get('HUIYAN_SESSION_PORT', 'default')
    return COOKIE + '_' + suffix if suffix.isdigit() else COOKIE + '_default'


class DesktopSessionGuard(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        secret = os.environ.get('HUIYAN_SESSION_TOKEN')
        if not secret:
            return await call_next(request)
        # Harmless readiness data is used by the packaged EXE smoke test.
        if request.url.path == '/api/health':
            return await call_next(request)
        if (request.method == 'GET' and request.url.path == '/'
                and hmac.compare_digest(request.query_params.get('session',''), secret)):
            response = RedirectResponse('/', status_code=303)
            response.set_cookie(_cookie_name(), secret, httponly=True, samesite='strict',
                                secure=False, path='/')  # localhost HTTP, not external TLS
            response.headers['Cache-Control'] = 'no-store'
            return response
        if hmac.compare_digest(request.cookies.get(_cookie_name(), ''), secret):
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response
        return JSONResponse({'detail': '慧眼会话已失效，请关闭并重新打开应用'},
                            status_code=401, headers={'Cache-Control':'no-store'})
