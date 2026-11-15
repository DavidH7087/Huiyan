# 慧眼 · 轻量中文离线语义模型 (Phase 7B)

慧眼可选使用 FastEmbed (ONNX Runtime) + `BAAI/bge-small-zh-v1.5`。Qdrant 文档标注该模型约 90MB、512 维，MIT 许可。**CPU 可运行，不需要 NVIDIA 显卡；在真正处理简历时不访问外网。**

该选项目前属于开发/技术预览：**基础 Windows 安装包暂未内置模型及 Python FastEmbed 依赖**。缺模型时程序自动回退关键词和 BM25，并明确显示未配置状态。

## 明确授权的一次性模型准备

```bash
python -m pip install -r requirements-fastembed.txt
python -m backend.fastembed_cpu prepare --cache-dir ./models/fastembed
```

这一命令只下载模型权重等公开资源，**不会上传或读取简历**。然后配置：

Linux / Codespaces:

```bash
export HUIYAN_FASTEMBED_CACHE_DIR="$(pwd)/models/fastembed"
export HF_HUB_OFFLINE=1
bash start.sh
```

Windows PowerShell (开发环境):

```powershell
$env:HUIYAN_FASTEMBED_CACHE_DIR = (Resolve-Path .\models\fastembed).Path
$env:HF_HUB_OFFLINE = '1'
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

状态检查：`/api/health` -> `semantic.state` 应为 `ready`（筛选后）或 `configured`（首次筛选前）。当 FastEmbed 启用且未安装额外精排时，语义检索用于**发现可能相关的原文段落**，不会增加“必要条件已证实”的数量，也不会自动拒绝候选人。

**严格离线保障：** 检索初始化使用 `local_files_only=True`；未准备权重、未安装依赖或模型损坏时错误会体现在 `/api/health`，基础功能保持可用。

本阶段还保留较重的 BGE-M3/SentenceTransformers 配置方式；两者优先级：若显式设置 `HUIYAN_EMBEDDING_MODEL`，优先使用该本地目录。不要将模型文件和候选人简历提交至公开仓库。

## 真实模型测试

单元测试使用本地桩并验证离线参数；专用 `Huiyan FastEmbed Real Model` 工作流会显式下载测试模型一次，随后设置 `HF_HUB_OFFLINE=1`，运行真实中文模型推理。该工作流通过与否才是“实际模型可用”的证据；不要把模拟测试冒充实际效果验收。
