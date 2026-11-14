"""File parsing with page-level provenance and optional offline PDF OCR."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from .ocr import MAX_OCR_PAGES, OcrUnavailable

SUPPORTED = {'.pdf', '.docx', '.txt'}
MAX_FILE = 25 * 1024 * 1024
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_MEMBERS = 500


class ParseError(ValueError):
    pass


def _docx_lines(container) -> list[str]:
    """Preserve paragraph/table order, including nested Word tables."""
    lines: list[str] = []
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            if block.text.strip():
                lines.append(block.text)
        elif isinstance(block, Table):
            for row in block.rows:
                cells: list[str] = []
                seen: set[int] = set()
                for cell in row.cells:
                    marker = id(cell._tc)
                    if marker in seen:
                        continue  # horizontally merged table cell
                    seen.add(marker)
                    text = '\n'.join(_docx_lines(cell)).strip()
                    if text:
                        cells.append(text)
                if cells:
                    lines.append(' | '.join(cells))
    return lines


def _pdf_pages(content: bytes, ocr=None) -> list[dict]:
    reader = PdfReader(io.BytesIO(content), strict=False)
    if len(reader.pages) > 120:
        raise ParseError('PDF 页数超过 120 页')
    ready = bool(ocr and ocr.status().get('state') == 'ready')
    pages: list[dict] = []
    attempts = 0
    for i, page in enumerate(reader.pages):
        extracted = page.extract_text() or ''
        record = {'page': i + 1, 'text': extracted, 'source': 'pdf_text' if extracted.strip() else 'unreadable'}
        # Very short PDF text layers may contain only page numbers or headers.
        weak_text = len(re.sub(r'\s+', '', extracted)) < 12
        if weak_text:
            if ready and attempts < MAX_OCR_PAGES:
                attempts += 1
                try:
                    recognized = ocr.recognize_pdf_page(content, i).strip()
                    if len(recognized) > len(extracted.strip()):
                        record.update(text=recognized, source='ocr', warning='本页文字由 OCR 识别，请核对原件')
                    elif not extracted.strip():
                        record['warning'] = 'OCR 没有识别出可用文字，请检查扫描质量'
                    else:
                        record['warning'] = '该页可提取的文字较少，请核对原件'
                except OcrUnavailable:
                    record['warning'] = '本页 OCR 识别失败，请检查原件或重新导入'
            else:
                record['warning'] = ('本页超过 OCR 处理上限，请单独检查' if ready else
                    '本页无可用文字或内容过少，若为扫描件请启用本地 OCR')
        pages.append(record)
    return pages


def _text_pages(name: str, content: bytes, ocr=None) -> list[dict]:
    suffix = Path(name).suffix.lower()
    if suffix == '.pdf':
        return _pdf_pages(content, ocr=ocr)
    if suffix == '.docx':
        doc = Document(io.BytesIO(content))
        return [{'page': 1, 'text': '\n'.join(_docx_lines(doc)), 'source': 'docx'}]
    if suffix == '.txt':
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('gb18030', errors='replace')
        return [{'page': 1, 'text': text, 'source': 'txt'}]
    raise ParseError('仅支持 PDF、DOCX、TXT 和包含这些格式的 ZIP')


def extract_pages(name: str, content: bytes, ocr=None) -> list[dict]:
    if len(content) > MAX_FILE:
        raise ParseError('单份文件超过 25MB')
    try:
        pages = _text_pages(name, content, ocr=ocr)
    except ParseError:
        raise
    except Exception:
        raise ParseError('文件无法读取或格式不完整') from None
    if not any(page['text'].strip() for page in pages):
        raise ParseError('未提取到文字；如果是扫描件，请启用本地 OCR 或重新扫描')
    return pages


def expand_upload(name: str, content: bytes):
    """Yield document name/bytes; prevent traversal, huge archives, encrypted archives."""
    if Path(name).suffix.lower() != '.zip':
        yield name, content
        return
    if len(content) > MAX_ARCHIVE:
        raise ParseError('ZIP 文件超过 100MB')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            items = [item for item in archive.infolist() if not item.is_dir()]
            if len(items) > MAX_MEMBERS:
                raise ParseError('ZIP 文件数量超过 500')
            cumulative = 0
            for info in items:
                filename = Path(info.filename.replace('\\', '/')).name
                if (not filename or info.filename.startswith(('/', '\\')) or
                    '..' in info.filename.replace('\\', '/').split('/')):
                    raise ParseError('ZIP 内存在不安全的文件路径')
                if Path(filename).suffix.lower() not in SUPPORTED:
                    continue
                cumulative += info.file_size
                if info.flag_bits & 0x1 or info.file_size > MAX_FILE or cumulative > MAX_ARCHIVE:
                    raise ParseError('ZIP 包含过大或加密的文件')
                yield filename, archive.read(info)
    except (zipfile.BadZipFile, RuntimeError, EOFError):
        raise ParseError('ZIP 无法读取') from None


def extract_identity(pages: list[dict], filename: str) -> dict:
    """Recognise explicitly labelled names and spaced Chinese mobile numbers.

    A resume heading such as '个人简历' must never become a candidate's name.
    """
    text = '\n'.join(page['text'] for page in pages)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = Path(filename).stem
    explicit = re.search(r'(?im)^\s*(?:姓名|name)\s*[：:]\s*([^\s|｜,，;；]{2,40})', text)
    if explicit:
        name = explicit.group(1)
    elif lines:
        head=lines[0].strip()
        if re.fullmatch(r'[\u3400-\u9fff]{2,4}', head) and head not in (
            '个人简历', '求职简历', '应聘简历', '简历', '联系方式', '基本信息'
        ):
            name = head
    emails = re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text)
    phones = re.findall(r'(?<!\d)1[3-9]\d(?:[\s-]?\d){8}(?!\d)', text)
    phone = re.sub(r'\D', '', phones[0]) if phones else ''
    return {'name': name[:80], 'email': emails[0] if emails else '', 'phone': phone}
