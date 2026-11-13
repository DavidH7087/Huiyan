"""Optional real OCR test; the GitHub OCR CI job installs Tesseract + languages."""
import io
import shutil

import pytest


def test_real_tesseract_pdf_render_and_ocr():
    if not shutil.which('tesseract'):
        pytest.skip('Tesseract executable not installed')
    pdfium = pytest.importorskip('pypdfium2')
    pytesseract = pytest.importorskip('pytesseract')
    PIL = pytest.importorskip('PIL.Image')
    from PIL import Image, ImageDraw, ImageFont
    from backend.ocr import LocalOcrService
    from backend.parsing import extract_pages

    ocr = LocalOcrService(enabled=True, language='eng')
    if ocr.status()['state'] != 'ready':
        pytest.skip('English Tesseract data unavailable')

    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not __import__('os').path.isfile(font_path):
        pytest.skip('Known test font unavailable')
    image = Image.new('RGB', (1500, 680), 'white')
    drawing = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, 55)
    drawing.text((80, 110), 'B2B SALES 2026', font=font, fill='black')
    drawing.text((80, 260), 'KEY ACCOUNT MANAGEMENT', font=font, fill='black')
    pdf = io.BytesIO()
    image.save(pdf, format='PDF', resolution=150)
    pages = extract_pages('scanned.pdf', pdf.getvalue(), ocr=ocr)
    assert pages[0]['source'] == 'ocr'
    assert 'B2B' in pages[0]['text']


def test_real_tesseract_chinese_scanned_pdf():
    """Synthetic Chinese résumé evidence tests local chi_sim (not accuracy in production)."""
    if not shutil.which('tesseract'):
        pytest.skip('Tesseract executable not installed')
    pytest.importorskip('pypdfium2')
    pytest.importorskip('pytesseract')
    pytest.importorskip('PIL.Image')
    import os
    from PIL import Image, ImageDraw, ImageFont
    from backend.ocr import LocalOcrService
    from backend.parsing import extract_pages

    font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    if not os.path.isfile(font_path):
        pytest.skip('Known CJK test font not installed')
    ocr = LocalOcrService(enabled=True, language='chi_sim+eng')
    if ocr.status()['state'] != 'ready':
        pytest.skip('Simplified Chinese Tesseract language data unavailable')
    image = Image.new('RGB', (2200, 950), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, 80)
    draw.text((100, 110), '企业客户开发', font=font, fill='black')
    draw.text((100, 360), '制造业客户管理', font=font, fill='black')
    pdf = io.BytesIO()
    image.save(pdf, format='PDF', resolution=190)
    pages = extract_pages('中文扫描.pdf', pdf.getvalue(), ocr=ocr)
    assert pages[0]['source'] == 'ocr'
    assert '企业客户开发' in pages[0]['text']
    assert '制造业客户管理' in pages[0]['text']
