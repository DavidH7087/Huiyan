"""Regression tests for files that HR users upload as real resumes."""
import io
from pathlib import Path
import pytest
from docx import Document
from docx.oxml import OxmlElement

from backend.ocr import LocalOcrService
from backend.parsing import ParseError, extract_pages


def test_docx_body_tables_and_footers():
    doc = Document()
    doc.add_paragraph('张示例')
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = '工作经历'
    table.cell(0, 1).text = '负责企业客户开发'
    doc.sections[0].footer.paragraphs[0].text = '熟悉工业品销售'
    f = io.BytesIO(); doc.save(f)
    result = extract_pages('candidate.docx', f.getvalue())
    text = '\n'.join(x['text'] for x in result)
    assert text.index('张示例') < text.index('企业客户开发')
    assert '熟悉工业品销售' in text


def test_docx_floating_text_box():
    doc = Document()
    p = doc.add_paragraph('个人简历')
    txbx = OxmlElement('w:txbxContent')
    para = OxmlElement('w:p')
    run = OxmlElement('w:r')
    t = OxmlElement('w:t'); t.text = '熟悉企业客户开发与项目管理'
    run.append(t); para.append(run); txbx.append(para)
    p._p.append(txbx)
    out = io.BytesIO(); doc.save(out)
    pages = extract_pages('textbox.docx', out.getvalue())
    assert '企业客户开发' in pages[0]['text']


def test_unreadable_pdf_reports_ocr_readiness():
    pytest.importorskip('PIL.Image')
    pytest.importorskip('reportlab')
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    image = Image.new('RGB', (700, 250), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((35, 75), 'Sales Developer - B2B accounts', fill='black')
    f = io.BytesIO(); c = canvas.Canvas(f, pagesize=(700, 250));c.drawImage(ImageReader(image),0,0,700,250);c.save()
    with pytest.raises(ParseError, match='OCR'):
        extract_pages('scanned.pdf', f.getvalue(), LocalOcrService(enabled=False))


def test_scanned_pdf_with_real_local_ocr_when_installed():
    pytest.importorskip('PIL.Image')
    pytest.importorskip('reportlab')
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    ocr=LocalOcrService()
    if ocr.status()['state'] != 'ready':
        pytest.skip('Local OCR not present')
    image = Image.new('RGB', (1200, 420), 'white')
    draw = ImageDraw.Draw(image)
    font_path = ('C:/Windows/Fonts/arial.ttf' if __import__('os').name == 'nt' else
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font=ImageFont.truetype(font_path,42) if Path(font_path).is_file() else None
    draw.text((35, 115), 'B2B SALES EXPERIENCE', fill='black', font=font)
    f = io.BytesIO(); c = canvas.Canvas(f, pagesize=(600, 210));c.drawImage(ImageReader(image),0,0,600,210);c.save()
    pages = extract_pages('scanned.pdf', f.getvalue(), ocr)
    assert pages[0]['source']=='ocr'
    assert 'SALES' in pages[0]['text'].upper()


def test_word_image_only_resume_needs_ocr_or_warning():
    pytest.importorskip('PIL.Image')
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1200, 600), 'white')
    draw = ImageDraw.Draw(image)
    font_path = ('C:/Windows/Fonts/arial.ttf' if __import__('os').name == 'nt' else
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font=ImageFont.truetype(font_path,42) if Path(font_path).is_file() else None
    draw.text((35, 140), 'EXPERIENCED BACKEND ENGINEER', fill='black', font=font)
    img=io.BytesIO();image.save(img,format='PNG');img.seek(0)
    doc=Document();doc.add_picture(img)
    out=io.BytesIO();doc.save(out)
    with pytest.raises(ParseError, match='OCR'):
        extract_pages('word-picture.docx', out.getvalue(), LocalOcrService(enabled=False))
    ocr=LocalOcrService()
    if ocr.status()['state']=='ready':
        pages=extract_pages('word-picture.docx', out.getvalue(), ocr)
        assert any(p['source']=='ocr' and 'ENGINEER' in p['text'].upper() for p in pages)


def test_invalid_word_and_pdf_are_usable_errors():
    for name in ('bad.pdf','bad.docx'):
        with pytest.raises(ParseError):
            extract_pages(name, b'not valid content')
