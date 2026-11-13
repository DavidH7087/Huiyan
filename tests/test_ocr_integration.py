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
