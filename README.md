# 慧眼 · 智能简历筛选助手

面向中国企业 HR 的**简洁、离线优先**的批量简历筛选软件。

> **开发状态：v0.7-preview Windows 本地测试版。** 目前具备 PDF/DOCX/TXT/ZIP 导入、文字证据检索、招聘任务/历史、人工审核、Excel 导出。**可选接入本地 BGE-M3 / Reranker**（需额外安装、配置且未做真实模型性能验收）；**已增加可选本地 Tesseract OCR**（仅在本机依赖就绪时自动启用，识别文本需人工核对）；**尚未集成** SmartResume、PaddleOCR、Qwen；**已有未签名的 Windows 安装器与便携测试包**（但未完成企业实机验收）。不应将当前文字匹配结果用作自动淘汰或录用决定。

## 在 GitHub Codespaces 运行

1. 在仓库 `main` 分支创建或打开 Codespace。
2. 在 Codespaces 终端运行：

```bash
pip install -r requirements.txt
bash start.sh
```

3. 打开自动转发的 **8000** 端口，即可使用慧眼。

可先上传 `examples/` 下的三份**完全虚构的测试简历**验证基础筛选流程。

**Phase 4B：合成简历测试集。** `testdata/synthetic/resumes_txt/` 已收录 120 份纯虚构简历，覆盖 6 类岗位，另含可复现的 DOCX/PDF/扫描件/ZIP 生成器、预期参考标签和测试脚本。完整多格式文件通过 `Huiyan Synthetic Corpus` GitHub Actions 生成可下载 ZIP。详见 [测试集说明](testdata/synthetic/README.md) 和 [阶段报告](docs/PHASE4B_SYNTHETIC_DATA_REPORT.md)。

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
- 二次筛选会保存新轮次；新增关键词或自由描述作为优先线索，可选择当前全部人选、优先查看、需要确认或人工面试名单，原轮次和人工审核记录保留。
- 默认基础模式没有向量语义推理；可选启用本地 BGE-M3 / Reranker 以检索**待核实的语义线索**。未配置模型时不会假装运行 AI。仍没有简历质量判断、OCR 或概率式评分。PDF 扫描图片若开启本地 OCR，则尽力提取并记录 OCR 来源；未启用或识别失败会列为失败文件。
- 在公司正式使用之前必须补充访问控制、数据保留/删除机制、加密、备份、隐私评估以及跨岗位人工验证。

## Phase 2A 已完成

可选本地语义模型的配置见 [`docs/MODEL_SETUP.md`](docs/MODEL_SETUP.md)。本轮实现范围、测试和限制见 [`docs/PHASE2_REPORT.md`](docs/PHASE2_REPORT.md)。**请只用虚构或合规脱敏样本在 Codespaces 开发测试，并确认转发端口为 Private。**

## Phase 2B 已完成

新增可选 Tesseract OCR 与逐页文字来源标记、Word 表格顺序提取、导入核对提示。配置见 [`docs/OCR_SETUP.md`](docs/OCR_SETUP.md)，报告见 [`docs/PHASE2B_REPORT.md`](docs/PHASE2B_REPORT.md)。

## Phase 2C：结构化候选人信息

当前可自动提取简历**明确写出的**学历词、部分技术技能、文字描述的工作年限和相关经历片段，每条信息保留页码/原文及 OCR 来源。它只是检索辅助，不是学历或技能核验，也不会推测性别、年龄或婚姻状况。`/api/tasks/{task_id}/resumes/{resume_id}/profile` 提供结构化 JSON，候选人阅读页可显示该信息。已导入的旧简历会在首次阅读时安全生成档案。

## Phase 3A：数据生命周期

已归档任务支持**输入完整名称确认**后永久删除，连同候选人、原简历文件、筛选记录及人工审核记录。API `DELETE /api/tasks/{id}` 需 JSON `{ "confirm_title": "任务名称" }`，如果文件无法删除则返回 `files_pending_cleanup` 并提示管理员；文件系统和数据库无法保证跨介质原子删除，**不代表安全擦除或磁盘不可恢复**。`GET /api/tasks/{id}/review-history` 可查看最近 500 条人工审核操作日志。请对 `data/` 做合规的访问控制、备份与保留策略；目前尚无用户登录、磁盘加密或企业权限系统。

## Windows 桌面测试构建（Phase 3B）

代码提交后，GitHub Actions 的 **Huiyan Windows Portable Build** 工作流会在 `windows-latest` 构建 `Huiyan-windows-x64-test-build`，可下载 ZIP 并解压运行 `Huiyan.exe`（Windows 11 / WebView2 Runtime）。这是**测试便携包，不是经过安全签名或人工验收的正式安装程序**；不会自动创建公开 Release。

桌面模式仅监听 `127.0.0.1`，数据默认存放在 `%LOCALAPPDATA%\Huiyan\data`。请阅读 [`docs/WINDOWS_BUILD.md`](docs/WINDOWS_BUILD.md)；该便携包暂不包含 Tesseract OCR 或语义大模型，若需 OCR，按 `docs/OCR_SETUP.md` 单独配置。CI 可检验打包可执行文件是否启动，但无法代替真实图形桌面和企业安全审查。

## Phase 3C：可恢复的批量导入

导入采用每份简历独立的 SQLite 事务，前端按最多 10 个文件一组上传，并显示处理进度；因意外中断而再次导入时，已保存的文件按内容哈希识别为重复，不会全部重做。`GET /api/tasks/{id}/imports` 返回最近 300 条导入状态。**注意：**单个大型 ZIP 内的处理进度仍不能实时展示；后台持久化任务队列和断点 OCR 续算尚未完成。

## Windows 安装器预览版（Phase 3E）

Windows 工作流另构建 Inno Setup 单文件安装包 `Huiyan-Setup-0.5.0-preview.exe`，并做静默安装后的 EXE 本机启动测试；使用 Windows 用户级目录安装，不需要管理员权限。卸载程序**不会自动擦除候选人档案**，数据仍在 `%LOCALAPPDATA%\Huiyan\data`。见 [`docs/INSTALLER_BUILD.md`](docs/INSTALLER_BUILD.md)。安装器未签名，仍属预览测试版。

## Phase 3D：候选人基础信息识别

识别明确写出的 `姓名：` 标签、电话中夹杂空格的中国大陆手机号；避免将“个人简历”等通用标题误识别为姓名。无足够依据时沿用文件名，不猜测姓名、年龄、性别等属性。

## Phase 4A：浏览器真实操作验收

新增 `Huiyan Browser E2E` 自动化工作流，通过 Playwright Chromium 实际点击首页、创建任务、上传虚构简历、筛选、审核和查看历史；测试成功保存 UI 截图到短期 GitHub Artifact。该测试不上传真实候选人资料，也不能替代 Windows WebView2 图形界面人工测试。

## Phase 5B：Windows 本地请求防护

Windows 桌面模式限制本地 Host 和跨站 Origin/FETCH 请求，降低其他网页读写本地招聘数据的风险；不替代企业多用户认证，详见 [Phase 5B 报告](docs/PHASE5B_REPORT.md)。

## Phase 5A：语境误匹配修复

新增保守的否定/培训/求职意向识别规则及 120 份合成样本的固定标签回归测试，详见 [`docs/PHASE5A_REPORT.md`](docs/PHASE5A_REPORT.md)。数据是合成样本，不代表真实招聘准确率。

## Phase 5E：跨格式候选人疑似重复提示

同任务中相同有效手机号或电子邮箱会提示疑似重复候选人，**不自动合并**或删除原文件，避免同名误伤。详见 [Phase 5E 报告](docs/PHASE5E_REPORT.md)。

## Phase 5D：安装说明和浏览器备份验收

更新 Windows 安装说明，Chromium 在严格桌面请求防护模式下覆盖加密备份下载，参见 [Phase 5D 报告](docs/PHASE5D_REPORT.md)。

## Phase 5C：密码保护的本地招聘档案备份

Windows 桌面版「招聘档案」页可创建 AES-256-GCM 加密备份 `.hyb`，包含招聘任务、简历原件、历史轮次及人工审核，恢复时必须使用独立的新数据目录，暂未提供普通 HR 的一键恢复向导。请阅读 [Phase 5C 开发报告](docs/PHASE5C_REPORT.md)，企业使用前须验证权限及备份恢复演练。

## 下一阶段

1. 评估 SmartResume / PaddleOCR 的中文简历结构化提取质量，完成大批量 OCR 队列。
2. 真实 BGE-M3 + Reranker 的离线推理测试与性能优化；目前已有可选适配层，尚未实测模型。
3. 可选本地 Qwen 解析自然语言条件；保证其输出必须由 HR 确认。
4. 可恢复的后台任务队列、进度展示、数据访问控制与备份。
5. Tauri 等 Windows 桌面打包方案，真正断网的安装及性能验收。

首个原型报告见 `docs/PHASE1_REPORT.md`，当前阶段报告见 `docs/PHASE2_REPORT.md`。

## Phase 4C：PDF / Word 测试库补全

针对「真实 PDF/DOCX 无法识别文字」反馈，测试集已扩大到 120 份 **DOCX**、120 份**文字 PDF**、12 份**图片扫描 PDF**及 120 TXT；在 [testdata/synthetic/fixtures](testdata/synthetic/fixtures) 可直接获取每种岗位的 PDF/DOCX 示例，完整文件在 GitHub Actions `Huiyan Synthetic Corpus` 工作流的 `Artifacts` 里。文件全部虚构且带基准标签，详见 [Phase 4C 报告](docs/PHASE4C_REPORT.md)。扫描 PDF 必须配合本地 OCR 才能识别，当前 Windows 预览版是否捆绑 OCR 需另行验证。

## Phase 4D：PDF/DOCX 识别修复

- **OCR 自动启用**：本机装好中文/英文 OCR 运行时即自动对扫描 PDF、图片式 DOCX 做本地识别，不再默认关闭；无依赖时普通文字文件仍能导入。Windows 安装版 OCR 随包提供的构建和验证在 Windows CI 中单独检查。
- **Word 提取**：支持正文、表格、页眉页脚、浮动文本框，并处理整页为图片的 DOCX。
- **诊断提示**：无法读出文字时显示 OCR 状态和实际原因，不默默当作空白简历。
- OCR 的提取内容均需要人工核实，不能直接判定岗位资格。详见 [OCR 使用说明](docs/OCR_SETUP.md) 及 [阶段报告](docs/PHASE4D_REPORT.md)。

## Phase 6B：可选排除线索与精确/同义关键词模式

每个招聘任务可分别配置「必须具备」「优先考虑」「排除线索」以及「关键词匹配方式」。排除命中只会标记为 HR 待核实，绝不自动删除候选人。扫描/OCR 提取仍需原件核对。关键词模式分为默认「智能同义」和「精确文字」（不扩展同义词）。已有招聘数据库自动迁移，旧轮次历史保持原样。Excel 导出附带排除线索列与匹配模式。详见 [`docs/PHASE6B_REPORT.md`](docs/PHASE6B_REPORT.md)。

## Phase 6A：Windows 可视化备份恢复

在本地桌面版「招聘档案」页面，选择 `.hyb` 备份、输入加密密码、填写“恢复”并上传；系统在新建独立目录完整解密验证，**不会覆盖当前正在使用的数据库**。关闭并重新打开慧眼后，自动切换到恢复档案；可从相同页面安排切回最初档案。恢复文件占用额外本地空间；当前未提供删除旧档案的自动按钮以避免误删。云端 Codespaces 禁用此恢复接口。详细报告见 [`docs/PHASE6A_REPORT.md`](docs/PHASE6A_REPORT.md)。

## Phase 4E：离线 Windows OCR 随包部署

Windows 构建会将 Tesseract OCR 与简体中文 / 英文语言数据打进安装器和便携包，扫描件识别无需云端 API。安装包完成前必须通过 Windows CI 的三项冒烟检查：源码启动、打包 EXE 启动、安装后 EXE 启动，而且三处都要求 `ocr.state=ready`。当前为 **v0.5.1-preview 候选**，请以对应工作流的通过结果为准，不代表真实简历识别准确性已经验收。
