"""Offline PDF/DOCX/TXT parsing with evidence provenance and automatic OCR fallback."""
from __future__ import annotations
import io
import re
import zipfile
from pathlib import Path
from pypdf import PdfReader
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
from .ocr import MAX_OCR_PAGES, OcrUnavailable

SUPPORTED = {'.pdf', '.docx', '.txt'}
MAX_FILE = 25 * 1024 * 1024
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_MEMBERS = 500

class ParseError(ValueError):
    pass

def _docx_lines(container) -> list[str]:
    """Keep table and paragraph order, including nested tables."""
    lines = []
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            if block.text.strip():
                lines.append(block.text)
        elif isinstance(block, Table):
            for row in block.rows:
                items, seen = [], set()
                for cell in row.cells:
                    key = id(cell._tc)
                    if key in seen:
                        continue
                    seen.add(key)
                    text = '\n'.join(_docx_lines(cell)).strip()
                    if text:
                        items.append(text)
                if items:
                    lines.append(' | '.join(items))
    return lines

def _docx_textboxes(doc) -> list[str]:
    """python-docx doesn't return Word floating textbox text in paragraphs."""
    result = []
    roots = [doc.part.element]
    for sec in doc.sections:
        roots.extend([sec.header._element, sec.footer._element])
    seen = set()
    for root in roots:
        for textbox in root.xpath('.//w:txbxContent'):
            for paragraph in textbox.iter(qn('w:p')):
                text = ''.join(node.text or '' for node in paragraph.iter(qn('w:t'))).strip()
                if text and text not in seen:
                    result.append(text)
                    seen.add(text)
    return result

def _validate_docx_archive(content: bytes) -> None:
    """Avoid expanding hostile, highly compressed Word files in memory."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.infolist()
        if len(members) > 1000:
            raise ParseError('Word 内部文件数量过多，已拒绝导入')
        total = 0
        for item in members:
            path = item.filename.replace('\\', '/')
            if path.startswith('/') or '..' in path.split('/'):
                raise ParseError('Word 包含不安全的内部文件路径')
            if item.flag_bits & 1:
                raise ParseError('Word 文档已加密，请先解除密码')
            total += item.file_size
            if total > MAX_ARCHIVE:
                raise ParseError('Word 解压后内容超过 100 MB，已拒绝导入')


def _docx_pages(content: bytes, ocr=None) -> list[dict]:
    _validate_docx_archive(content)
    doc = Document(io.BytesIO(content))
    lines = _docx_lines(doc)
    for section in doc.sections:
        for area in (section.header, section.footer):
            lines.extend(_docx_lines(area))
    lines.extend(_docx_textboxes(doc))
    raw = '\n'.join(lines).strip()
    records = [{'page': 1, 'text': raw, 'source': 'docx'}] if raw else []
    ready = bool(ocr and ocr.status().get('state') == 'ready')
    # Some job-board exports are Word containers with the entire resume as an image.
    # Only OCR media if text is sparse, to avoid reading logos from normal DOCX.
    if len(re.sub(r'\s+', '', raw)) < 60:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                pictures = [i for i in z.infolist() if i.filename.startswith('word/media/')
                            and Path(i.filename).suffix.lower() in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')]
                pictures = [i for i in pictures if i.file_size <= MAX_FILE][:8]
                if pictures and not ready:
                    warning = 'Word 中包含图片形式的简历；本地 OCR 不可用，不能确认图片中的文字'
                    if records:
                        records[0]['warning'] = warning
                    else:
                        records = [{'page': 1, 'text': '', 'source': 'unreadable', 'warning': warning}]
                elif pictures and ready:
                    recognized = []
                    for item in pictures:
                        try:
                            text = ocr.recognize_image(z.read(item))
                            if text.strip():
                                recognized.append(text)
                        except OcrUnavailable:
                            pass
                    if recognized:
                        records.append({'page': 1, 'text': '\n'.join(recognized), 'source': 'ocr',
                                        'warning': 'Word 嵌入图片中的 OCR 文字，需要核对原件'})
        except (zipfile.BadZipFile, RuntimeError, OSError):
            pass
    return records or [{'page': 1, 'text': '', 'source': 'unreadable'}]

def _is_suspicious(text: str) -> bool:
    """Catch PDFs with long *fake* text layers caused by broken font mappings."""
    visible = re.sub(r'\s+', '', text or '')
    if not visible:
        return False
    n = len(visible)
    if len(re.findall(r'(?i)\(?cid:\d+\)?', visible)) >= 2:
        return True
    if sum(0xE000 <= ord(c) <= 0xF8FF for c in visible) >= max(5, int(n * .20)):
        return True
    if sum(c in '\ufffd\u25a1\u25a0' for c in visible) >= max(5, int(n * .20)):
        return True
    return False


def _is_weak(text: str) -> bool:
    visible = re.sub(r'\s+', '', text or '')
    return len(visible) < 12 or _is_suspicious(text)

def _pdf_pages(content: bytes, ocr=None) -> list[dict]:
    reader = PdfReader(io.BytesIO(content), strict=False)
    if len(reader.pages) > 120:
        raise ParseError('PDF 页数超过 120 页')
    ready = bool(ocr and ocr.status().get('state') == 'ready')
    pages, attempts = [], 0
    for i, page in enumerate(reader.pages):
        try:
            extracted = page.extract_text() or ''
        except Exception:
            extracted = ''
        bad_layer = _is_suspicious(extracted)
        record = {'page': i + 1, 'text': '' if bad_layer else extracted,
                  'source': 'pdf_text' if extracted.strip() and not bad_layer else 'unreadable'}
        if _is_weak(extracted):
            if ready and attempts < MAX_OCR_PAGES:
                attempts += 1
                try:
                    recognized = ocr.recognize_pdf_page(content, i).strip()
                    if (recognized and not _is_suspicious(recognized)
                            and (bad_layer or len(recognized) > len(extracted.strip()) or '\ufffd' in extracted)):
                        record.update(text=recognized, source='ocr', warning='本页文字由 OCR 识别，需核对原件')
                    else:
                        record['warning'] = ('PDF 文字层乱码且 OCR 未读出可靠文字' if bad_layer else
                                             'PDF 页面文字较少或扫描不清楚，请核对原件')
                except OcrUnavailable:
                    record['warning'] = '该页 OCR 识别失败，请检查原件'
            else:
                record['warning'] = ('超出每份文件 OCR 页数上限，请单独检查' if ready else
                                     'PDF 可能为扫描件图片或文字编码异常：当前 OCR 未就绪')
        pages.append(record)
    return pages

def _text_pages(name: str, content: bytes, ocr=None) -> list[dict]:
    suffix = Path(name).suffix.lower()
    if suffix == '.pdf':
        return _pdf_pages(content, ocr)
    if suffix == '.docx':
        return _docx_pages(content, ocr)
    if suffix == '.txt':
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('gb18030', errors='replace')
        return [{'page': 1, 'text': text, 'source': 'txt'}]
    raise ParseError('只支持 PDF、DOCX、TXT 和包含这些格式的 ZIP；旧版 .doc 请先转换为 DOCX')

def extract_pages(name: str, content: bytes, ocr=None) -> list[dict]:
    if len(content) > MAX_FILE:
        raise ParseError('单份文件超过 25 MB')
    try:
        pages = _text_pages(name, content, ocr)
    except ParseError:
        raise
    except Exception:
        raise ParseError('文件无法读取或格式不完整；加密 PDF 请先解除密码') from None
    if not any(p.get('text', '').strip() for p in pages):
        kind = Path(name).suffix.lower()
        if kind in ('.pdf', '.docx'):
            note = next((p['warning'] for p in pages if p.get('warning')), '')
            if not note:
                note = '文件可能为扫描图片、文字编码异常或内容为空'
            ocr_state = ocr.status() if ocr is not None else {'state':'unavailable'}
            if ocr_state.get('state') != 'ready':
                note += '；本地 OCR 状态：' + ocr_state.get('message', '未安装')
            raise ParseError('未提取到文字（无法识别文字）：' + note)
        raise ParseError('文档没有可读取的文字')
    return pages

def expand_upload(name: str, content: bytes):
    if Path(name).suffix.lower() != '.zip':
        yield name, content
        return
    if len(content) > MAX_ARCHIVE:
        raise ParseError('ZIP 文件超过 100 MB')
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

# Chinese heading words that can look like short personal names.
_NOT_PERSON_NAMES = (
    '个人简历', '个人资料', '求职简历', '应聘简历', '自我介绍', '基本信息',
    '联系方式', '联系电话', '求职意向', '应聘职位', '应聘岗位', '教育背景',
    '教育经历', '工作经历', '工作经验', '项目经历', '技能特长', '专业技能',
    '姓 名', '姓名', '简历', '候选人', '应聘者', '应聘人', '销售经理',
    '招聘专员', '产品经理', '开发工程师', '软件工程师', '信息技术',
    '实习经历', '自我评价', '个人评价', '职业经历', '个人信息',
    '负责', '联系', '熟悉', '掌握', '参与', '项目', '教育', '学历', '技能',
    '工作', '管理', '开发', '背景', '简介', '概况', '摘要',
)


def _person_name(raw: str) -> str:
    """Accept a plausible visible name, never infer one from a job title."""
    if re.match(r'^(?:联系电话|联系(?:方式|人)|手机(?:号码|号)?|电话|邮箱|'
                r'电子邮箱|邮件地址|应聘岗位|应聘职位|求职意向)\s*[:：|｜\t ]',
                raw.strip(), flags=re.I):
        return ''
    text = re.split(
        r'[|｜,，;；\t]|(?:电话|手机|邮箱|性别|年龄|求职意向|应聘岗位|'
        r'学历|Email|Phone)\s*[:：]', raw.strip(), maxsplit=1, flags=re.I
    )[0].strip().strip(' :：')
    text = re.sub(r'^(?:先生|女士)\s*', '', text)
    # Chinese headers may contain separated characters: '张 三'.
    zh = re.match(r'^([\u3400-\u9fff](?:\s*[\u3400-\u9fff]){1,5})(?=\s|$)', text)
    if zh:
        value = re.sub(r'\s+', '', zh.group(1))
    elif re.fullmatch(r'[\u3400-\u9fff]{2,6}(?:·[\u3400-\u9fff]{2,6})?', text):
        value = text
    elif re.fullmatch(r"[A-Za-z][A-Za-z'’-]{1,24}(?:\s+[A-Za-z][A-Za-z'’-]{1,24}){1,3}", text):
        value = ' '.join(text.split())
    else:
        return ''
    if len(value) > 30 or value in _NOT_PERSON_NAMES:
        return ''
    if value.casefold() in {
        'resume', 'curriculum vitae', 'work experience', 'sales manager',
        'sales developer', 'customer development', 'software engineer',
        'professional summary', 'personal profile', 'personal information',
        'contact information', 'project experience',
    }:
        return ''
    if any(s in value for s in (
        '简历', '招聘', '岗位', '工作', '经验', '求职', '经理', '客户',
        '职位', '应聘', '候选', '工程师', '专业', '学历', '联系方式',
        '毕业', '销售', '开发', '公司', '项目', '学校', '电话',
    )):
        return ''
    return value


def _name_from_resume(pages: list[dict]) -> str:
    lines = []
    for page in pages[:3]:
        lines.extend(line.strip() for line in page.get('text', '').splitlines() if line.strip())
        if len(lines) >= 120:
            break
    lines = lines[:120]
    for i, line in enumerate(lines):
        # Explicit labels take priority even when a resume starts with a heading.
        m = re.match(r'^\s*(?:姓\s*名|full\s*name|name)\s*[:：|｜\t ]+\s*(.+)$',
                     line, flags=re.I)
        if m:
            extracted = _person_name(m.group(1))
            if extracted:
                return extracted
        if re.fullmatch(r'(?:姓\s*名|full\s*name|name)\s*[:：]?', line, flags=re.I):
            if i+1 < len(lines):
                extracted = _person_name(lines[i+1])
                if extracted:
                    return extracted
    for line in lines[:7]:
        # A heading followed by a person's name on the next line is common.
        if line.replace(' ', '') in _NOT_PERSON_NAMES:
            continue
        candidate = _person_name(line)
        if candidate:
            return candidate
    return ''


def extract_identity(pages: list[dict], filename: str) -> dict:
    text = '\n'.join(page.get('text', '') for page in pages)
    name = _name_from_resume(pages)
    emails = re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text)
    phones = re.findall(r'(?<!\d)1[3-9]\d(?:[\s-]?\d){8}(?!\d)', text)
    return {'name': name or '姓名待确认',
            'name_source': 'extracted' if name else 'unknown',
            'email': emails[0] if emails else '',
            'phone': re.sub(r'\D', '', phones[0]) if phones else ''}
