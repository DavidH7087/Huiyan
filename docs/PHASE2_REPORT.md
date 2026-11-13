# 慧眼 · Phase 2A 开发报告（2026-11-13）

## 本轮目标

从 v0.1 文字证据筛选原型进入可选离线语义检索，并改善全岗位关键词的基本准确性和多轮工作管理。

## 本轮实际实现

1. 新增 `backend/semantic.py`：可配置本地 SentenceTransformer Embedding 模型、可选 CrossEncoder Reranker。只读取本地目录，默认不下载模型；将结果标记为待人工核实的语义线索。
2. 新增 `requirements-ai.txt`，可选依赖与基础依赖分开；新增 `docs/MODEL_SETUP.md` 明确安装、模型状态和隐私要求。
3. `backend/engine.py` 为未命中直接文字的条件提供独立 `semantic_hint`，不将向量相似度伪装成证明，不因缺失信息自动淘汰候选人。
4. `backend/app.py` 在健康接口暴露语义模块状态；自然语言二次筛选即使没有词典关键词，也会保留为待检索的优先描述。
5. 二次筛选新增来源范围选择：当前轮次全部 / 优先查看 / 需要确认 / 人工面试名单，保留原筛选轮次，并在历史中标记来源范围。
6. 关键词证据检索改为逐句定位，修复 `JavaScript` 错当 `Java` 的问题，并改进证据原文片段。
7. `frontend/app.js` 显示“可能相关的经历，需要人工核实”，不展示虚假的 AI 能力分数；本地模型失效时提醒回退基础匹配。

## 已验证

- Python 自动测试：17/17 通过（包括语义检索假模型、模型缺失回退、自然语言跟进、分支范围筛选、人工审核保存、技术词边界）。
- 前端 JavaScript：`node --check frontend/app.js` 通过。
- 真实 BGE-M3 / Reranker 尚未加载运行；新增的语义适配层已通过注入假模型的逻辑测试，**不能宣称真实模型效果已通过验收**。

## 未完成 / 后续

- 在有足够内存的实际 Codespace 或 Windows 电脑上运行 BGE-M3/Reranker 模型，测量速度、资源占用及匹配质量。
- 真正的 BM25 中文全文检索、批次 embedding 缓存与任务后台队列。
- SmartResume/PaddleOCR 的中文扫描简历结构化识别。
- 更完善的自然语言条件理解（可选本地 Qwen），OCR 不可用时的信息质量提示。
- 企业安全：身份验证、敏感信息保护、数据保留与删除、审计与备份。
- Windows 桌面壳、离线安装包和非技术 HR 的可用性测试。

## 使用说明

基础模式：`pip install -r requirements.txt && bash start.sh`。可选本地语义模型见 `docs/MODEL_SETUP.md`。
