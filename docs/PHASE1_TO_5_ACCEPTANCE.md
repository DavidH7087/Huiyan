# 慧眼 v0.9.0-preview · Phase 1–5 综合验收记录

> 状态：**候选版本 / 未签名内部预览**。此记录只说明已实现的功能与可验证方式，**并不宣称已经完成企业商用发布验收**。
> 所有测试使用完全虚构数据；不得把真实个人简历上传公开 GitHub/Codespaces。

## 已实现 / 自动化可验证

| 阶段 | 核心实现 | 自动化验收 | 仍待外部验收 |
| --- | --- | --- | --- |
| Phase 1 自然语言与混合筛选 | 仅凭描述创建岗位；描述线索限量、HR 可编辑/清空；必须/优先/排除条件独立保存；可选逐项精确匹配；更改不覆盖旧轮次 | `tests/test_description_screening.py`、`tests/test_description_clue_edits.py`、`tests/test_semantic.py` | 多岗位真实脱敏样本精度/召回率、歧义与否定语句、职业同义词的人工标注评估 |
| Phase 2 完整招聘历史 | 轮次筛选快照、两轮候选人和分组比较、复用旧条件生成新轮次、恢复旧轮次到岗位设置、编辑/恢复操作审计、人工审核状态快照 | `tests/test_round_history.py`、`tests/test_task_change_history.py`、Chromium E2E | 历史批量导出、招聘人员对“当前审核”与“历史审核”的可理解性观察 |
| Phase 3 批量导入 | 拖入文件、文件夹输入、每批 10 份上传、导入日志、问题明细和失败文件重试；哈希去重与每文件单独数据库提交 | `tests/test_format_ingestion.py`、`tests/test_bulk_500_smoke.py`、Chromium E2E | 真实不同版式 PDF/DOCX/扫描件、500–1000 份混合文件及 OCR 的时间/内存压力测试；崩溃后异步任务恢复 |
| Phase 4 隐私与档案安全 | 本地 Host/Origin/会话保护；加密 .hyb 备份和隔离恢复；单候选人永久删除；候选人保留期限只读检查；SQLite 和原件完整性统计 | `tests/test_session_security.py`、`tests/test_backup.py`、`tests/test_candidate_erasure.py`、`tests/test_retention_diagnostics.py` | 企业身份/权限体系、Windows 磁盘/数据库静态加密、内部备份管理、信息保留政策、合法性评估 |
| Phase 5 Windows 安装与发布准备 | 基础版/AI 版本号统一 `0.9.0-preview`；构建 Windows 便携包与安装器；真实 OCR、AI 版 ONNX 推理、安装后 EXE 冒烟、卸载不删除数据、SHA256 与依赖清单 | GitHub Actions: CI、Browser E2E、Windows Portable Build、Windows AI Model Edition Build | 实际 Windows 11 WebView2 可见窗口、安装/升级/卸载人工验收、代码签名/SmartScreen、第三方软件及模型许可、商业发布审批 |

## 功能性原则

1. **离线优先。** 岗位和简历默认只存在本地部署环境；本地模型推理只读取设备内已有权重。
2. **人工决策。** “优先查看”“需要确认”只表示证据检索线索；不得作为自动淘汰或录用依据。未发现某项文字证据并不证明候选人没有该技能。
3. **历史可信。** 新一轮筛选使用快照，不更改旧轮次。当前人工审核与创建轮次时的审核状态分别呈现；旧格式若没有快照则明确说明未知。
4. **隐私保守。** 保留期限检查不执行自动删除。删除原文件会调整关联历史候选人数；离线加密备份文件不受当前数据库删除同步影响，需根据企业制度处理。

## 发布阻断条件（不得由绿色 CI 推断为已完成）

- [ ] 在真实 Windows 11 机器打开 **可见的** WebView2 窗口，人工完成完整 HR 工作流，并测试关闭后重开、升级和卸载
- [ ] 在获得合法授权的真实脱敏招聘文档上做人工标签、精度/召回率、误拒风险、中文不同岗位及 OCR 评测
- [ ] 验证企业权限、静态加密、个人数据保留/删除政策、自动备份与档案恢复演练
- [ ] 完成第三方软件/ONNX 模型许可核查、源码许可证政策、商标风险核查与软件供应链审计
- [ ] 获取可信代码签名证书，完成 SmartScreen/Defender 和其他安全软件兼容检查
- [ ] 明确商业发布责任人与验收人，审核结论后才可创建正式 GitHub Release

### CI 与交付位置

- 开发 PR：https://github.com/DavidH7087/Huiyan/pull/1
- GitHub Actions：https://github.com/DavidH7087/Huiyan/actions
- 所有安装器在 Actions Artifacts 中，默认标记为 **unsigned-internal-preview**，属于测试产物。
- 不要在交付材料里写“测试 500 份真实简历”；`tests/test_bulk_500_smoke.py` 使用的是自动生成的 500 份 TXT 人造资料。

## 本轮主要改动文件

- `backend/engine.py` — 自然语言线索
- `backend/app.py`、`backend/storage.py` — 岗位设置迁移、筛选快照、回退/比较/复用、审核审计和保留期限
- `backend/diagnostics.py` — 只读本地数据完整性检查
- `frontend/app.js`、`frontend/styles.css`、`frontend/index.html` — 极简 HR 工作流与导航
- `.github/workflows/*.yml`、`packaging/*.iss` — PR 端到端测试和 Windows 安装包验证
- `tests/*.py` — 回归测试与自动化操作

## 后续真实验收应记录的证据

每台实际 Windows 设备应记录：Windows 版本、WebView2 版本、CPU/内存、软件版本、启动截图、导入 OCR 记录、断网测试、安装/卸载结果、安全软件告警、备份恢复演练、脱敏标签评测和对应负责人；结果不应包含候选人敏感信息。
