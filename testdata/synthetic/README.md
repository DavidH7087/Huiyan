# 慧眼 · 完全虚构的中文简历测试集

**所有内容由模板生成，不对应任何真实求职者或企业。** 邮箱使用 `example.invalid`，电话为不可拨通的 `000-0000-0000`，没有身份证、住址等信息。禁止作为真实招聘记录。

## 数据规模与内容

- `resumes_txt/`：120 份即时可导入的 TXT 简历，6 类岗位 × 每类 20 份。
- `jobs.json`：6 类岗位的岗位说明及要求，可复制到慧眼的「开始简历筛选」。
- `truth.json`：逐人预设场景标签（仅用于自动测试，不是客观人才评分）。
- `build_corpus.py`：以固定规则生成全部文本与多格式变体：120 DOCX、120 可提取文字 PDF、12 图片扫描 PDF、20 ZIP（包括重复文件）以及 3 个故意损坏/空文件。
- `benchmark.py`：调用慧眼现有规则引擎与参考标签对比，输出逐份明细和错误分类。

## GitHub 中直接可下载的 PDF 与 DOCX

`fixtures/` 内有每个岗位各一份真实 DOCX 和可复制文字 PDF、两份扫描图片 PDF。**完整的 120 DOCX + 120 PDF + 12 扫描 PDF** 可通过自动生成工作流下载，而不是只保留 TXT；生成后可以在慧眼中分别验证每种格式。

## 生成多格式样本

在仓库根目录执行：

```bash
python -m pip install -r requirements-fixtures.txt
python testdata/synthetic/build_corpus.py --out testdata/synthetic/generated
python testdata/synthetic/benchmark.py --root testdata/synthetic/generated
```

在 Linux Codespace 内生成中文 PDF，可能需先安装中文字体：

```bash
sudo apt-get update
sudo apt-get install -y fonts-arphic-gbsn00lp fonts-noto-cjk
```

`generated/` 已被 Git 忽略，内含实际 PDF、DOCX、扫描件、ZIP 和 `benchmark/summary.md`。也可以从 GitHub Actions **Huiyan Synthetic Corpus** 流水线直接下载完整 ZIP，完全不用在 Codespace 中安装本地字体。

若只想生成 120 份文本，执行：

```bash
python testdata/synthetic/build_corpus.py --out testdata/synthetic/generated --text-only
```

## 六种岗位与测试规则

| 岗位 | 必须具备 | 加分 |
|---|---|---|
| 企业客户销售经理 | B2B销售、客户开发 | 制造业、渠道拓展 |
| Java 后端工程师 | Java、SQL | 团队管理 |
| Python 数据分析师 | Python、SQL | 团队管理 |
| 总账会计 | 财务核算 | SQL |
| 招聘专员 | 招聘 | 团队管理 |
| 仓储库存主管 | 库存管理 | SQL |

每组 20 份包含明确匹配 6 份、同义表述匹配 4 份、明确否定 3 份、描述不足 3 份、可迁移能力 2 份、培训关键词但无实际经历 1 份、混合语境 1 份。

## 实测发现的已知问题

在最初的基础文字匹配引擎上，120 份合成样本的测试发现 22 份被错误归类为「优先查看」：因否定句、培训提到关键词、描述含有岗位职责但没有独立实践等语境造成。详情见 `docs/PHASE4B_SYNTHETIC_DATA_REPORT.md` 和运行生成的 `benchmark/summary.md`。

**这些数字不是实际招聘精度，也没有经过独立招聘专家标注。** 这些测试用来发现回归与误筛；真实 HR 仍需核对证据，不能自动淘汰候选人。

不要将 120 份 TXT 与它们的 DOCX/PDF 变体全部导入同一招聘任务统计候选人数，因为那会造成跨格式同一人被算作多份候选人。
