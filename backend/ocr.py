"""Optional Tesseract OCR for scanned PDFs. Never uploads content externally."""
from __future__ import annotations

import os
import shutil

MAX_OCR_PAGES = 30
MAX_IMAGE_PIXELS = 10_000_000


class OcrUnavailable(RuntimeError):
    """Missing local OCR dependencies, data or an unsuccessful recognition."""


class LocalOcrService:
    def __init__(self, enabled: bool | None = None, language: str | None = None):
        self.enabled = (os.getenv('HUIYAN_OCR_ENABLED', '0') == '1') if enabled is None else enabled
        self.language = language or os.getenv('HUIYAN_OCR_LANG', 'chi_sim+eng')
        self._state = self._check()

    def _check(self) -> dict:
        if not self.enabled:
            return {'state': 'disabled', 'message': '未开启扫描件识别'}
        if not shutil.which('tesseract'):
            return {'state': 'unavailable', 'message': '尚未安装本地 Tesseract OCR 程序'}
        try:
            import pypdfium2  # noqa: F401
            import pytesseract
            available = set(pytesseract.get_languages(config=''))
        except Exception as exc:
            return {'state': 'unavailable', 'message': 'OCR 依赖未就绪：' + type(exc).__name__}
        missing = set(self.language.split('+')) - available
        if missing:
            return {'state': 'unavailable', 'message': '缺少 OCR 语言数据：' + ', '.join(sorted(missing))}
        return {'state': 'ready', 'message': '本地扫描件识别已就绪', 'language': self.language}

    def status(self) -> dict:
        return self._state.copy()

    def recognize_pdf_page(self, content: bytes, page_number: int) -> str:
        """Render one zero-indexed PDF page and run local OCR with a time limit.

        This method is intentionally synchronous; background queues are future work.
        """
        if self._state['state'] != 'ready':
            raise OcrUnavailable(self._state['message'])
        import pypdfium2 as pdfium
        import pytesseract
        try:
            document = pdfium.PdfDocument(content)
            try:
                if page_number < 0 or page_number >= len(document):
                    raise OcrUnavailable('PDF 页码不正确')
                page = document[page_number]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise OcrUnavailable('PDF 页面尺寸不正确')
                    scale = min(2.2, (MAX_IMAGE_PIXELS / (width * height)) ** .5)
                    if scale < .4:
                        raise OcrUnavailable('PDF 页面过大，无法安全识别')
                    bitmap = page.render(scale=scale)
                    try:
                        with bitmap.to_pil().convert('RGB') as image:
                            return pytesseract.image_to_string(
                                image, lang=self.language, config='--psm 3', timeout=30
                            ).strip()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            finally:
                document.close()
        except OcrUnavailable:
            raise
        except Exception as exc:
            # Do not leak filenames, file content or machine configuration in UI errors.
            raise OcrUnavailable('扫描页面识别失败（' + type(exc).__name__ + '）') from None
