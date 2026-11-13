# 慧眼 · 可选离线扫描件 OCR (Phase 2B)

## 说明

目前使用本机 **Tesseract OCR + PDFium** 做扫描版 PDF 的第一页到第 30 个弱文字页面识别。仅当 PDF 页面文字层很少时才启动 OCR；对已能正确提取的页面不增加 OCR 负担。识别出的内容会标为「OCR文字待核实」，不能直接作为满足必要条件的证明。

这是一套**已实现的本地 OCR 基线**，不是 PaddleOCR，且不能保证复杂中文扫描件的识别正确率。之后仍需用脱敏样本比较 PaddleOCR 和 Tesseract 的效果。

## GitHub Codespaces / Debian Linux 配置

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
python -m pip install -r requirements-ocr.txt
export HUIYAN_OCR_ENABLED=1
bash start.sh
```

检查是否已就绪：打开页面后访问 `/api/health`，查看 `ocr.state` 应为 `ready`。启动后增加依赖需要重启服务。Tesseract 和语言数据已经安装好后，识别不会调用互联网 API。

## Windows 环境

在本机安装 Tesseract OCR（确保有 `chi_sim` 和 `eng` 训练数据），将 `tesseract.exe` 目录加入 `PATH`，执行 `pip install -r requirements-ocr.txt`。在 PowerShell 中设置：

```powershell
$env:HUIYAN_OCR_ENABLED = "1"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

正式 Windows 安装程序尚未制作；需要验证 Tesseract 与语言包的本地捆绑及许可。

## 设计限制

- 每个 PDF 最多识别 30 个文字层过少的页面；其余页面会留下警告，防止无止境 OCR 任务。
- 单张 PDF 渲染控制在约 1,000 万像素以内，识别进程有超时限制；当前导入流程仍然是同步请求，暂不适合无人值守的大批量 OCR。
- 某页即使识别成功，结果也标记为 OCR 文字，并在候选人详情提示人工核对原文件；个别页失败会有导入警告。
- 扫描件全部无法识别时会拒绝导入并报告原因，绝不当作一份空白简历参加筛选。
- 不默认开启 OCR，以确保缺少大型依赖的普通办公电脑仍能使用文本简历筛选。
- Codespaces 是云端环境，不要上传公司真实简历；正式运行需本地化及个人信息安全评估。
