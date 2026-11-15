"""Native Windows Excel export: authenticated loopback fetch and atomic save.

The WebView2 download manager is not relied upon. Users pick an explicit path,
and a success response is emitted only after a validated XLSX exists on disk.
"""
from __future__ import annotations

import io
import os
import tempfile
import zipfile
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

MAX_XLSX_BYTES = 30 * 1024 * 1024


class ExportError(Exception):
    pass


def save_excel_file(base_url: str, token: str, task_id: int, run_id: int,
                    destination: str | Path, *, opener=None) -> dict:
    if (not isinstance(task_id, int) or isinstance(task_id, bool) or task_id < 1
            or not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1):
        raise ExportError("筛选任务或轮次无效")
    if not base_url.startswith("http://127.0.0.1:"):
        raise ExportError("Excel 仅允许从本机慧眼服务导出")
    path = Path(destination)
    if path.suffix.lower() != ".xlsx":
        raise ExportError("请保存为 .xlsx Excel 文件")
    if not path.parent.is_dir():
        raise ExportError("所选保存目录不存在")
    if path.is_symlink():
        raise ExportError("不允许覆盖符号链接")
    client = opener or build_opener(HTTPCookieProcessor(CookieJar()))
    try:
        # Desktop session cookie is HttpOnly and per-port, the same as the WebView.
        with client.open(Request(base_url + "/?" + urlencode({"session": token})),
                         timeout=10):
            pass
        endpoint = f"{base_url}/api/tasks/{task_id}/runs/{run_id}/export"
        with client.open(Request(endpoint), timeout=90) as response:
            media = response.headers.get("Content-Type", "")
            if "spreadsheetml" not in media:
                raise ExportError("导出服务返回了非 Excel 数据")
            data = response.read(MAX_XLSX_BYTES + 1)
    except (OSError, TimeoutError) as exc:
        raise ExportError("无法从本机筛选服务读取 Excel，请重试") from exc
    if not data or len(data) > MAX_XLSX_BYTES:
        raise ExportError("导出文件为空或超过大小限制")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as workbook:
            names = set(workbook.namelist())
            if not {"[Content_Types].xml", "xl/workbook.xml"}.issubset(names):
                raise ExportError("导出文件不是有效的 Excel 工作簿")
            if workbook.testzip() is not None:
                raise ExportError("导出 Excel 文件校验失败")
    except zipfile.BadZipFile as exc:
        raise ExportError("导出文件损坏") from exc
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".huiyan-export-",
                                         suffix=".xlsx", dir=path.parent,
                                         delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        raise ExportError("保存 Excel 失败，请检查路径或文件是否被占用") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    if path.stat().st_size != len(data):
        raise ExportError("保存后文件大小不一致")
    return {"ok": True, "filename": path.name, "bytes": len(data)}
