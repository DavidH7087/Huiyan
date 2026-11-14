"""Local OCR for image PDF and image-only DOCX files; never uses a cloud API."""
from __future__ import annotations

import io
import os
import shutil
import sys
from pathlib import Path

MAX_OCR_PAGES = 30
MAX_IMAGE_PIXELS = 10_000_000


class OcrUnavailable(RuntimeError):
    pass


class LocalOcrService:
    def __init__(self, enabled: bool | None = None, language: str | None = None):
        # Auto-on when all offline dependencies are installed. Explicit 0 disables OCR.
        self.enabled = (os.getenv('HUIYAN_OCR_ENABLED', 'auto').lower() not in ('0', 'false', 'off')) if enabled is None else enabled
        self.language = language or os.getenv('HUIYAN_OCR_LANG', 'chi_sim+eng')
        self._state = self._check()

    @staticmethod
    def _binary() -> str | None:
        # The Windows portable and installed bundles ship a private OCR runtime.
        if getattr(sys, 'frozen', False):
            bundled = Path(sys.executable).resolve().parent / 'ocr' / 'tesseract.exe'
            if bundled.is_file():
                return str(bundled)
        configured = os.getenv('HUIYAN_TESSERACT_PATH')
        if configured and Path(configured).is_file():
            return configured
        path = shutil.which('tesseract')
        if path:
            return path
        if os.name == 'nt':
            for root in (os.getenv('ProgramFiles'), os.getenv('LOCALAPPDATA')):
                if root:
                    candidate = Path(root) / 'Tesseract-OCR' / 'tesseract.exe'
                    if candidate.is_file():
                        return str(candidate)
        return None

    def _check(self) -> dict:
        if not self.enabled:
            return {'state': 'disabled', 'message': '扫描件识别已关闭（HUIYAN_OCR_ENABLED=0）'}
        binary = self._binary()
        if not binary:
            return {'state': 'unavailable', 'message': '扫描件需要本地 OCR：当前未安装 Tesseract。普通文字 PDF 和 Word 不受影响。'}
        try:
            import pypdfium2  # noqa: F401
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = binary
            bundled_dir = Path(binary).parent / 'tessdata'
            if bundled_dir.is_dir():
                # Tesseract 5 resolves traineddata relative to this tessdata directory.
                os.environ['TESSDATA_PREFIX'] = str(bundled_dir)
            available = set(pytesseract.get_languages(config=''))
        except Exception as exc:
            return {'state': 'unavailable', 'message': '本地 OCR 依赖尚未就绪：' + type(exc).__name__}
        missing = set(self.language.split('+')) - available
        if missing:
            return {'state': 'unavailable', 'message': '缺少 OCR 语言包：' + ', '.join(sorted(missing))}
        return {'state': 'ready', 'message': '本地中文与英文 OCR 已就绪', 'language': self.language}

    def status(self) -> dict:
        return self._state.copy()

    def _image_to_text(self, image) -> str:
        import pytesseract
        if image.width * image.height > MAX_IMAGE_PIXELS:
            shrink = (MAX_IMAGE_PIXELS / (image.width * image.height)) ** 0.5
            image = image.resize((max(1, int(image.width * shrink)), max(1, int(image.height * shrink))))
        return pytesseract.image_to_string(image.convert('RGB'), lang=self.language, config='--psm 3', timeout=30).strip()

    def recognize_image(self, content: bytes) -> str:
        if self._state['state'] != 'ready':
            raise OcrUnavailable(self._state['message'])
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(content)) as image:
                return self._image_to_text(image)
        except Exception as exc:
            raise OcrUnavailable('嵌入图片 OCR 失败：' + type(exc).__name__) from None

    def recognize_pdf_page(self, content: bytes, page_number: int) -> str:
        if self._state['state'] != 'ready':
            raise OcrUnavailable(self._state['message'])
        import pypdfium2 as pdfium
        try:
            document = pdfium.PdfDocument(content)
            try:
                if not (0 <= page_number < len(document)):
                    raise OcrUnavailable('PDF 页码不正确')
                page = document[page_number]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise OcrUnavailable('PDF 页面尺寸不正确')
                    scale = min(2.2, (MAX_IMAGE_PIXELS / (width * height)) ** 0.5)
                    if scale < 0.4:
                        raise OcrUnavailable('扫描页面像素超出处理上限')
                    bitmap = page.render(scale=scale)
                    try:
                        with bitmap.to_pil().convert('RGB') as image:
                            return self._image_to_text(image)
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            finally:
                document.close()
        except OcrUnavailable:
            raise
        except Exception as exc:
            raise OcrUnavailable('PDF 扫描识别失败：' + type(exc).__name__) from None
