# 慧眼 · 可选的本地语义模型

> 当前为开发选项，不是默认要求。**完全不安装 AI 模型，原来的简历导入、文字证据筛选、历史和导出仍可使用。**

## 支持的能力

安装后，慧眼会对未找到直接关键词证据的条件，使用本地 Embedding 查找相近的简历经历；可选的 Reranker 进一步挑选相关段落。

**语义相似不代表具备资格。** 新发现的结果以“可能相关的经历（需要人工核实）”显示，不作为直接满足必要条件的证据。

## 在 Codespaces 准备模型（仅开发测试）

先在仓库根目录安装可选依赖：

```bash
pip install -r requirements-ai.txt
```

只有在**明确选择安装**时，下载模型到本地 `models/` 目录：

```bash
hf download BAAI/bge-m3 --local-dir ./models/bge-m3
# 可选；资源较紧张的 Codespace 可以先不装精排模型
hf download BAAI/bge-reranker-v2-m3 --local-dir ./models/bge-reranker-v2-m3
```

在 Codespaces 终端启用（只使用模型本地目录，不会在处理简历期间自动下载）：

```bash
export HUIYAN_EMBEDDING_MODEL="$(pwd)/models/bge-m3"
export HUIYAN_RERANKER_MODEL="$(pwd)/models/bge-reranker-v2-m3"  # 可选
bash start.sh
```

请根据实际安装情况设置变量：如果**没有下载 Reranker**，就不要设置 `HUIYAN_RERANKER_MODEL`。首次筛选时加载模型，可能较慢。BGE-M3 和 Reranker 都相对占用内存，普通 Codespace 可能不够，建议先对少量**虚构样本**测试。

Windows 本地运行时同样可以将模型保存在指定目录，并将环境变量设置为模型目录的**绝对路径**。实际发行前还需要设计友好的模型安装入口与硬件检测。

## 检查状态

打开 `/api/health`，查看 `semantic.state`：

| 状态 | 含义 |
|---|---|
| `not_configured` | 未设置模型，使用基础文字匹配 |
| `configured` | 已设置本地目录，首次筛选时加载 |
| `ready` | 模型已加载，启用语义候选证据 |
| `error` | 缺依赖、路径错误或模型不兼容，回退基础模式 |

对于 `error`，系统会在结果页面给出简明提示，不假装已经完成语义分析。

## 安全边界

- 不提交 `models/`、`data/` 或真实简历到仓库。
- Codespaces 是云环境，**不等于公司本地离线部署**。
- GitHub Codespaces 的端口必须保持 **Private**；该开发原型还没有企业访问控制。
- 模型读取限制为明确配置的本地目录，并使用 `local_files_only=True` 和 `trust_remote_code=False`。
- 语义相关性仅用于寻找面试核查线索，不表示工作成果真实，也不是录用概率。
- 在进行正式招聘前必须经过跨岗位人工验收、隐私评估与权限控制测试。
