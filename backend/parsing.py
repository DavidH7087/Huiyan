"""File parsing and safety boundaries. Files are never uploaded to third parties."""
from __future__ import annotations
import io
import re
import zipfile
from pathlib import Path
from pypdf import PdfReader
from docx import Document

SUPPORTED={".pdf", ".docx", ".txt"}
MAX_FILE=25*1024*1024
MAX_ARCHIVE=100*1024*1024
MAX_MEMBERS=500

class ParseError(ValueError):
    pass


def _text_pages(name: str, content: bytes) -> list[dict]:
    suffix=Path(name).suffix.lower()
    if suffix==".pdf":
        reader=PdfReader(io.BytesIO(content), strict=False)
        if len(reader.pages)>120:
            raise ParseError("PDF 页数超过 120 页")
        return [{"page": i+1,"text":page.extract_text() or ""} for i,page in enumerate(reader.pages)]
    if suffix==".docx":
        doc=Document(io.BytesIO(content))
        parts=[p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return [{"page":1,"text":"\n".join(parts)}]
    if suffix==".txt":
        try:
            text=content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text=content.decode("gb18030",errors="replace")
        return [{"page":1,"text":text}]
    raise ParseError("仅支持 PDF、DOCX、TXT 和包含这些格式的 ZIP")


def extract_pages(name: str, content: bytes) -> list[dict]:
    if len(content)>MAX_FILE:
        raise ParseError("单份文件超过 25MB")
    try:
        pages=_text_pages(name,content)
    except ParseError:
        raise
    except Exception:
        raise ParseError("文件无法读取或格式不完整") from None
    if not any(p['text'].strip() for p in pages):
        raise ParseError("未提取到文字；扫描件 OCR 将在后续版本支持")
    return pages


def expand_upload(name: str, content: bytes):
    """Yield document name/bytes; prevent traversal, huge archives, encrypted archives."""
    if Path(name).suffix.lower()!=".zip":
        yield name,content
        return
    if len(content)>MAX_ARCHIVE:
        raise ParseError("ZIP 文件超过 100MB")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            items=[i for i in z.infolist() if not i.is_dir()]
            if len(items)>MAX_MEMBERS:
                raise ParseError("ZIP 文件数量超过 500")
            cumulative=0
            for info in items:
                filename=Path(info.filename.replace('\\','/')).name
                if not filename or info.filename.startswith(("/","\\")) or ".." in info.filename.replace('\\','/').split('/'):
                    raise ParseError("ZIP 内存在不安全的文件路径")
                if Path(filename).suffix.lower() not in SUPPORTED:
                    continue
                cumulative+=info.file_size
                if info.flag_bits & 0x1 or info.file_size>MAX_FILE or cumulative>MAX_ARCHIVE:
                    raise ParseError("ZIP 包含过大或加密的文件")
                yield filename,z.read(info)
    except (zipfile.BadZipFile, RuntimeError, EOFError):
        raise ParseError("ZIP 无法读取") from None


def extract_identity(pages: list[dict], filename: str) -> dict:
    text="\n".join(p['text'] for p in pages)
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    name=Path(filename).stem
    if lines and len(lines[0])<=12 and not any(ch.isdigit() for ch in lines[0]):
        name=lines[0]
    emails=re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",text)
    phones=re.findall(r"(?<!\d)1[3-9]\d{9}(?!\d)",text)
    return {"name":name[:80],"email":emails[0] if emails else "","phone":phones[0] if phones else ""}
