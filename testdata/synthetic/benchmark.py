#!/usr/bin/env python3
"""Compare Huiyan's rule-based retrieval with fixed synthetic *scenario labels*.

Important: synthetic labels are NOT real hiring suitability or measured field accuracy.
Use 'python testdata/synthetic/benchmark.py --root ...' from repo root.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def run(root: Path) -> tuple[dict, list[dict]]:
    from backend.parsing import extract_pages
    from backend.engine import evaluate
    jobs = {job['id']:job for job in json.loads((root/'jobs.json').read_text(encoding='utf-8'))}
    cases = json.loads((root/'truth.json').read_text(encoding='utf-8'))
    stats=Counter(); by_role=defaultdict(Counter); by_scenario=defaultdict(Counter); rows=[]
    for record in cases:
        path=root/'txt'/record['file']
        pages=extract_pages(path.name,path.read_bytes())
        job=jobs[record['job_id']]
        prediction=evaluate(job['required'],job['preferred'],pages)
        expected=record['human_expected_group']
        actual=prediction['group']
        key='TP' if expected=='优先查看' and actual=='优先查看' else ('FN' if expected=='优先查看' else ('FP' if actual=='优先查看' else 'TN'))
        stats[key]+=1
        by_role[record['job_id']][key]+=1
        by_scenario[record['scenario']][key]+=1
        rows.append({'id':record['id'],'job_id':record['job_id'],'scenario':record['scenario'],
                     'expected':expected,'predicted':actual,'confusion':key,'matched_terms':
                     [check['term'] for check in prediction['checks'] if check['evidence']]})
    total=len(rows); positives=stats['TP']+stats['FP']
    summary={'dataset':'completely fictitious resumes, synthetic scenario labels',
             'n':total,'confusion':{k:stats[k] for k in ['TP','FP','FN','TN']},
             'precision_on_synthetic':round(stats['TP']/positives,4) if positives else None,
             'recall_on_synthetic':round(stats['TP']/(stats['TP']+stats['FN']),4) if stats['TP']+stats['FN'] else None,
             'false_priority_count':stats['FP'],'true_priority_count':stats['TP'],
             'by_role':{key:dict(value) for key,value in sorted(by_role.items())},
             'by_scenario':{key:dict(value) for key,value in sorted(by_scenario.items())},
             'warning':'Cannot estimate performance on actual resumes; labels are template-authored, not independent expert judgments.'}
    return summary,rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default='testdata/synthetic/generated')
    parser.add_argument('--out',default=None)
    args=parser.parse_args()
    root=Path(args.root)
    summary, rows=run(root)
    out=Path(args.out) if args.out else root/'benchmark'
    out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    (out/'predictions.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['# 慧眼合成简历基准测试结果','',
           '> 这些参考标签由合成模板预设，不是实际招聘适用性评估。下列比例仅用于发现规则引擎缺陷，不能作为真实准确率。','',
           f'- 测试简历：{summary["n"]} 份；岗位：6 类',
           f'- 正确标为优先查看：{summary["confusion"]["TP"]}',
           f'- 错误标为优先查看：{summary["confusion"]["FP"]}',
           f'- 需要优先但未标记：{summary["confusion"]["FN"]}',
           f'- 正确标为需要确认：{summary["confusion"]["TN"]}',
           f'- 合成集优先查看查准率：{summary["precision_on_synthetic"]:.1%}',
           f'- 合成集优先查看查全率：{summary["recall_on_synthetic"]:.1%}',
           '', '## 误判案例（需要确认却列为优先）','',
           '| 编号 | 岗位 | 情形 | 检出的文字条件 |', '|---|---|---|---|']
    for row in rows:
        if row['confusion']=='FP':
            lines.append(f'| {row["id"]} | {row["job_id"]} | {row["scenario"]} | {"、".join(row["matched_terms"])} |')
    lines+=['','**后续重点：** 改进否定语气、关键词出现在课程/培训语境、岗位参与与独立负责的区别、证明不足的经历。','']
    (out/'summary.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    # Scripts live under testdata/synthetic, but are called from repo root.
    repo=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(repo))
    main()
