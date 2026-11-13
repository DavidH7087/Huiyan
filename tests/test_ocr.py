"""OCR parser tests do not require system OCR or model downloads."""
import io

import pytest
from docx import Document
from pypdf import PdfWriter

from backend.ocr import LocalOcrService, OcrUnavailable
from backend.parsing import ParseError, extract_pages
from backend.engine import evaluate


def blank_pdf():
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(output)
    return output.getvalue()


class FakeOcr:
    def status(self):
        return {'state': 'ready'}

    def recognize_pdf_page(self, content, page_number):
        assert page_number == 0
        return '张三\n负责工业设备销售及制造企业客户开发\n熟悉B2B销售'


def test_scanned_pdf_uses_local_ocr_and_marks_source():
    pages = extract_pages('扫描简历.pdf', blank_pdf(), ocr=FakeOcr())
    assert pages[0]['source'] == 'ocr'
    assert '客户开发' in pages[0]['text']
    assert '核对原件' in pages[0]['warning']
    evaluation = evaluate(['客户开发'], [], pages)
    assert evaluation['group'] == '需要确认'
    assert evaluation['checks'][0]['evidence']['source'] == 'ocr'
    assert evaluation['checks'][0]['state'] == 'OCR文字待核实'


def test_scanned_pdf_without_local_ocr_is_reported_not_discarded_silently():
    with pytest.raises(ParseError, match='扫描件'):
        extract_pages('扫描简历.pdf', blank_pdf())
    assert LocalOcrService(enabled=False).status()['state'] == 'disabled'


def test_ocr_failure_on_a_blank_scan_remains_import_error():
    class Broken(FakeOcr):
        def recognize_pdf_page(self, *args):
            raise OcrUnavailable('bad')
    with pytest.raises(ParseError, match='未提取到文字'):
        extract_pages('损坏.pdf', blank_pdf(), ocr=Broken())


def test_docx_paragraph_table_order():
    document = Document()
    document.add_paragraph('张三')
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = '工作经历'
    table.cell(0, 1).text = '制造业销售'
    document.add_paragraph('最后一段：客户开发')
    buf = io.BytesIO()
    document.save(buf)
    pages = extract_pages('候选人.docx', buf.getvalue())
    text = pages[0]['text']
    assert text.index('张三') < text.index('工作经历') < text.index('制造业销售') < text.index('最后一段')
    assert pages[0]['source'] == 'docx'


def test_pdf_metadata_error_is_not_false_match():
    result = evaluate(['客户开发'], [], [{'page': 1, 'text': '客户开发', 'source': 'ocr'}])
    assert result['required_met_textually'] == 0
    assert result['checks'][0]['state'] == 'OCR文字待核实'
