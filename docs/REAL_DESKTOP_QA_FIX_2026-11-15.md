# 慧眼 v0.9.1-preview｜Windows 实机问题专项修复报告

测试依据：2026-11-15《慧眼 Windows 桌面实测报告》（用户 Library 文件 Huiyan_Desktop_Test_2026-11-15.md）。

**性质：针对合成样本的缺陷修复。不是商用招聘质量或 WebView2 实机二次验收。**

## 发现的问题和修复方案

| 实测问题 | 修复 | 验收依据 |
| --- | --- | --- |
| “招聘B2B销售”把“招聘”当作必须能力 | 区分招聘动作与人事招聘能力；保留“校园招聘经验”等真实 HR 条件 | `test_hiring_word_not_mistaken_for_recruitment_skill` |
| “没有B2B销售经验，也没有客户开发经验”被称为语义相关经历 | 语义检索结果增加否定表达拦截；界面将否定原句作为**否定线索**供人工核对，不当作正向能力证据 | `test_semantic_negative_never_shown_as_positive_experience` |
| Python 后端开发误关联客户开发 | 对客户开发/B2B销售补充领域锚点；仅出现“开发”等泛词不能形成正向语义提示 | `test_semantic_python_backend_does_not_imply_customer_development` |
| 手工与自动线索重复，5 个能力算作 7 个 | 新轮次会把旧自动提取短语规范化为单独能力，与手工必须/优先条件按同义能力去重，必要条件优先；既有历史轮次不重写 | `test_distinct_textual_skills_count_once_even_with_legacy_clues`、API 测试 |
| “5年B2B销售与企业客户开发经验”年限未显示 | 结构化资料解析规则 `rules-v2` 识别岗位/技能年限，并与总工作年限分开描述；旧缓存按版本更新 | `test_skills_years_are_distinguished_from_total_work_years` |
| Windows Excel 点击无文件保存反馈 | WebView2 增加 Python JS API 原生保存对话框，经本地授权会话获取数据并校验 XLSX ZIP 工作簿后原子写盘；仅在写盘成功后提示成功。网页版本改为显式下载与提示 | `test_desktop_excel_export.py` 与 Chromium E2E 浏览器下载验证 |
| 创建新轮次后页面停留在中下方 | 新轮次完成自动滚动到结果顶部 | Chromium 全流程验证 |

## 数据兼容性

- 不覆盖用户保留的测试任务、5 份合成简历、3 轮筛选和审核记录。
- 旧轮次结果保留原始快照。**重新创建一轮筛选**，才能使用新版筛选条件去重和语义过滤规则。
- 再次打开旧简历时，结构化信息采用 `rules-v2` 重新计算并写回缓存。
- Windows AI 版仍属于本地中文向量检索，语义提示必须人工核实，不做自动淘汰。

## 测试覆盖和边界

- Python/API 全量 pytest、OCR 集成测试、JavaScript 语法检查。
- Chromium 端到端真实点击 Excel 导出并读取下载的 .xlsx 工作簿。
- Windows PR 流水线真实打包、安装和卸载可在 GitHub Actions 中检查；其 EXE 烟雾测试**不打开可见 WebView2 窗口**。
- 原生 Windows “另存为”窗口的实际弹出、目标路径落盘及企业权限/防护软件仍须在用户 Windows 11 实机手动复测。
- 扫描件 OCR、真实异形 PDF/DOCX、大批量性能、关闭重启后的数据持续性仍属于独立未完成验收项。

代码：<https://github.com/DavidH7087/Huiyan/pull/2>。

## 建议实机复测顺序

1. 确保当前安装目录的本地招聘数据已按需备份，安装修复版，不手动删除 `%LOCALAPPDATA%\Huiyan\data`。
2. 用保留的原测试任务新增一轮筛选，确认条件不再重复、否定/无关经历不再出现正向语义提示。
3. 打开 5 年经验简历，确认“岗位/技能年限：5”。
4. 在新轮次点击 **导出 Excel**，选择明确的本地目录，确认磁盘有 .xlsx 文件，并用 Excel 打开检查候选人数和表头。
5. 关闭程序再启动，检查 3 个原轮次、新轮次和人工审核备注仍在。
