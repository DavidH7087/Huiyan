# 慧眼 · 智能简历筛选助手

面向中国企业 HR 的**简洁、离线优先**的批量简历筛选软件。

> **开发状态：v0.1 可运行的本地原型。** 目前具备 PDF/DOCX/TXT/ZIP 导入、文字证据检索、招聘任务/历史、人工审核、Excel 导出。**尚未集成** OCR、SmartResume、BGE-M3、Reranker、Qwen；**尚未打包 Windows 安装程序**。不应将当前文字匹配结果用作自动淘汰或录用决定。

## 在 GitHub Codespaces 运行

1. 在仓库 `main` 分支创建或打开 Codespace。
2. 在 Codespaces 终端运行：

```bash
pip install -r requirements.txt
bash start.sh
```

3. 打开自动转发的 **8000** 端口，即可使用慧眼。

可先上传 `examples/` 下的三份**完全虚构的测试简历**验证基础筛选流程。

打开后，可依次测试：输入岗位描述 → 确认关键词 → 创建任务 → 导入简历 → 开始筛选 → 逐项查看文字证据 → 人工审核 → 导出 Excel → 查看历史轮次。

本地数据存放在 `data/`；**此目录已加入 `.gitignore`，严禁上传真实个人简历到代码仓库或提交到 Git。** 注意 Codespaces 是云端开发环境，因此在 Codespaces 上传真实简历**并不等于保存在公司电脑上**。在企业授权及个人信息合规措施落实前，请只使用模拟或脱敏简历测试。实际断网运行应部署在本地电脑，而非 Codespaces。

## 本地运行

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

在浏览器访问 `http://127.0.0.1:8000`。当前为本地 Web 预览，Windows 桌面壳和离线安装包是后续工作。若需自定义保存位置，可设置环境变量 `HUIYAN_DATA_DIR`。

## 测试

```bash
pip install pytest httpx
python -m pytest -q
```

## 当前匹配机制与限制

- HR 提供必要条件、优先条件，也可输入自由文本作为提示，软件提供小型术语词典辅助解析。
- 对每项条件，检索简历原文与有限的行业同义词，保留原始页码及引用片段。
- **找到相关文字 ≠ 经历真实，更不等于能力已得到证明。** 无相关文字时显示“待核实”，不自动删除简历。
- 二次筛选会保存新轮次；新增关键词作为优先线索，原轮次和人工审核记录保留。
- 目前没有真正的向量语义推理、简历质量判断、OCR 或概率式评分。PDF 的扫描图片如果无法提取文字会列为失败文件。
- 在公司正式使用之前必须补充访问控制、数据保留/删除机制、加密、备份、隐私评估以及跨岗位人工验证。

## 下一阶段

1. 文件预处理和 OCR、结构化信息提取（评估 SmartResume / PaddleOCR）。
2. 本地 BGE-M3 + Reranker 的语义证据检索，经过测评再替换基础检索。
3. 可选本地 Qwen 解析自然语言条件；保证其输出必须由 HR 确认。
4. 可恢复的后台任务队列、进度展示、数据访问控制与备份。
5. Tauri 等 Windows 桌面打包方案，真正断网的安装及性能验收。

具体完成范围见 `docs/PHASE1_REPORT.md`。
