# 慧眼 · Phase 2B 开发报告（2026-11-13）

## 开发目标

解决扫描版 PDF 无文字层时无法导入的问题，改善 Word 表格与正文的提取顺序，明确哪些匹配依据来自 OCR，而不是把扫描识别当成已证实的经历。

## 代码改动

- `backend/ocr.py`：新增可选本地 Tesseract + PDFium OCR 适配器，支持简体中文与英文、每页超时、渲染像素上限、OCR 运行状态检测、无依赖时的安全回退。
- `backend/parsing.py`：对 PDF 逐页先读文字层，文字过少时按需 OCR；每页保存来源及核对警告。Word 采用 `iter_inner_content` 保留段落、表格顺序，支持嵌套表格。
- `backend/app.py`：在导入接口处理 OCR、记录警告并在候选人结果与健康检查接口暴露状态。OCR 计算在工作线程中执行，不长时间占用异步事件循环。
- `backend/engine.py`：证据携带来源，OCR 命中显示 `OCR文字待核实`，不会直接满足硬性招聘条件。即使没找到相关文字也不会自动淘汰候选人。
- `frontend/app.js`：导入后显示「需核对」文件及 OCR 风险提示，候选人详情显示 OCR 来源。
- `requirements-ocr.txt` 与 `docs/OCR_SETUP.md`：可选安装步骤及 Codespaces/Windows 本地启用说明。

## 验证范围

- 在本地测试环境中，使用真实 Tesseract + PDFium 对纯图片 PDF 的**中文与英文**内容进行了端到端扫描识别验证。GitHub OCR 集成任务包含真实扫描件回归测试。
- 在单元测试中，使用可控的模拟中文 OCR 结果验证来源标记、必要条件不被误认、OCR 不可用时的安全回退。
- Word 混合段落/表格顺序测试、PDF 页码处理、既有 API 测试继续纳入 GitHub Actions 回归。
- 本阶段**尚未证明真实中文招聘简历的 OCR 准确率**；需要脱敏样本进行准确性测试。

## 未完成

- 大量文件的后台任务队列与持久化进度。
- PaddleOCR 与复杂多栏 PDF 的效果评测，DOCX 内嵌图片 OCR。
- OCR 误识别的人工原文校对编辑工具。
- Windows 一键安装程序、权限控制、简历隐私合规及数据保留/清理。
