"""PDF text-layer corruption must not silently masquerade as parsed CV text."""
import pytest
import backend.parsing as parsing


class DummyPdf:
    def __init__(self, text):
        self.pages = [type('Page', (), {'extract_text': lambda self: text})()]


class OcrStub:
    def __init__(self, outcome='张示例\n在制造业负责企业客户开发'):
        self.outcome = outcome
        self.calls = []

    def status(self):
        return {'state':'ready','message':'synthetic OCR'}

    def recognize_pdf_page(self, content, page):
        self.calls.append(page)
        return self.outcome


@pytest.mark.parametrize('bad', [
    chr(0xE000) * 45,   # broken private-use font mapping
    '(cid:123)(cid:124)(cid:125)(cid:126)',  # font CID mapping leak
    '\u25a1' * 50,  # missing-glyph boxes
    '\ufffd' * 24,  # replacement chars
])
def test_unreadable_pdf_text_layer_triggers_ocr_even_if_long(monkeypatch,bad):
    monkeypatch.setattr(parsing, 'PdfReader', lambda *a,**k: DummyPdf(bad))
    ocr=OcrStub()
    pages=parsing.extract_pages('resume.pdf',b'%PDF mocked',ocr)
    assert len(pages)==1 and pages[0]['source']=='ocr'
    assert '客户开发' in pages[0]['text']
    assert pages[0]['warning']
    assert ocr.calls==[0]


@pytest.mark.parametrize('bad',[chr(0xE000)*40,'(cid:123)'*10,'\u25a1'*30])
def test_unreadable_pdf_without_ocr_is_rejected(monkeypatch,bad):
    monkeypatch.setattr(parsing, 'PdfReader', lambda *a,**k: DummyPdf(bad))
    with pytest.raises(parsing.ParseError,match='未提取到文字'):
        parsing.extract_pages('bad.pdf',b'%PDF mocked')


def test_normal_Chinese_text_layer_is_preserved_without_ocr(monkeypatch):
    resume='张示例\n曾担任 B2B 销售主管，负责工业客户开发与渠道建设，具有实际项目经验。'
    monkeypatch.setattr(parsing, 'PdfReader',lambda *a,**k: DummyPdf(resume))
    ocr=OcrStub()
    pages=parsing.extract_pages('normal.pdf',b'%PDF mocked',ocr)
    assert pages[0]['source']=='pdf_text'
    assert pages[0]['text']==resume
    assert ocr.calls==[]


def test_corrupt_ocr_output_fails_instead_of_accepting_garbage(monkeypatch):
    monkeypatch.setattr(parsing, 'PdfReader',lambda *a,**k:DummyPdf(chr(0xE000)*30))
    with pytest.raises(parsing.ParseError,match='未提取到文字'):
        parsing.extract_pages('corrupt.pdf',b'%PDF mocked',OcrStub(chr(0xE001)*31))
