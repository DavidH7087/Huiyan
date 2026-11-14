"""Origin and Host boundaries for the loopback-only desktop service.

This protects against browser cross-site requests and common DNS-rebinding
attempts. It does not provide OS account isolation or protection from local
malware, and is not an authentication system for a hosted service.
"""
from __future__ import annotations

import re

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_LOCAL_HOST = re.compile(r'^(?:127\.0\.0\.1|localhost)(?::\d{1,5})?$', re.IGNORECASE)


class DesktopRequestGuard(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host = request.headers.get('host', '')
        if not _LOCAL_HOST.fullmatch(host):
            return JSONResponse({'detail': '本地服务仅允许本机访问'}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin.lower() != f'http://{host.lower()}':
            return JSONResponse({'detail': '已拒绝其他网页的请求'}, status_code=403)
        if request.headers.get('sec-fetch-site', '').lower() in ('cross-site', 'same-site'):
            return JSONResponse({'detail': '已拒绝跨站请求'}, status_code=403)
        return await call_next(request)
