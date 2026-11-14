# 慧眼 · PDF / Word 文字识别与本地 OCR

## 先区分文件类型

- **文字版 PDF**：通常能在 PDF 阅读器选中并复制文字，慧眼会直接提取。若字体编码损坏、无 Unicode 映射，也可能需要 OCR。
- **扫描版 PDF**：PDF 每页是图片，不存在文字层；必须运行 OCR 才能识别。
- **普通 DOCX**：从正文、表格、页眉页脚和浮动文字框读取文字。
- **图片式 DOCX**：若整页简历为嵌入图片，慧眼在本地 OCR 就绪时尝试识别；无法正确识别的内容会留待核对。
- **旧版 DOC（非 DOCX）**：暂不支持，请用 Word/LibreOffice 转换为 DOCX 后再导入。

## 自动 OCR 的工作方式

只要 Tesseract、`chi_sim`/`eng` 语言包、`pypdfium2` 和 `pytesseract` 已在本机就绪，OCR **自动启用**（`HUIYAN_OCR_ENABLED=auto`）。强制关闭可设置 `HUIYAN_OCR_ENABLED=0`。OCR 始终在本地执行，不将简历发往任何模型 API。

PDF 逐页先尝试读取文本层，只对没有可用文本或疑似乱码的页面使用 OCR；最多 30 页，单页有像素与超时上限。OCR 提取会保留 `source=ocr` 和“需人工核对”警告；绝不能把 OCR 命中直接当作满足硬性岗位要求。

## Windows 安装版（v0.5.1 预览候选）

Windows CI 在打包过程中安装 Tesseract 和简体中文、英文语言模型，再将运行时打进安装包和便携包。**以 Windows 构建和启动测试实际通过为准**，不能因为提交了打包脚本就认为已经随包部署成功。

运行后可通过本机 `/api/health` 检查 `ocr.state=ready`；如果是 `unavailable`，导入页面会提示 OCR 尚未就绪，扫描件不可识别。

## GitHub Codespaces (Debian Linux)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
python -m pip install -r requirements-ocr.txt
bash start.sh
```

切记：Codespaces 是云端环境，不要上传公司真实简历。需要在本地 Windows 软件测试私有简历。

## 尚未解决的情况

复杂多栏排版、异体字、极低分辨率扫描、密码保护 PDF、图片严重模糊都可能需要人工处理。首次装完组件若程序已经启动，需要重启慧眼。OCR 可读不等于字段正确，应与 PDF 原件比较。
