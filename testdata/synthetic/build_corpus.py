#!/usr/bin/env python3
"""Reproducible, entirely fictional Chinese resume benchmark for Huiyan.

Usage: python testdata/synthetic/build_corpus.py --out /tmp/huiyan-corpus
Optional binary fixture dependencies: reportlab, python-docx, Pillow.
This script never downloads or fabricates real personal information.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import zipfile
from collections import Counter
from pathlib import Path

ROLES = [
    {"id":"b2b_sales","title":"企业客户销售经理","required":["B2B销售","客户开发"],"preferred":["制造业","渠道拓展"],
     "strong":"负责 B2B 销售，独立完成客户开发，为制造业企业提供工业设备解决方案，负责渠道拓展。",
     "synonym":"主要从事工业品销售，自主开发制造企业新客户，拓展工厂采购部门及经销商开发网络。",
     "negative":"没有 B2B 销售经历；未曾从事客户开发，过去主要在零售门店做收银工作。",
     "partial":"负责企业客户的售后问题处理和合同归档，没有说明是否承担客户开发或企业销售目标。",
     "transfer":"参与工厂客户的产品咨询及售后服务协调，帮助销售团队准备商务材料，但不承担客户开发责任。",
     "unrelated":"曾做零售收银与门店排班，日常处理顾客咨询，未涉及企业销售。",
     "stuff":"课程大纲出现 B2B销售、客户开发 两个关键词，但本人尚无相关岗位经历。",
     "hybrid":"负责制造企业客户服务；曾参加 B2B销售 培训，但没有独立客户开发经历。"},
    {"id":"java_backend","title":"Java 后端工程师","required":["Java","SQL"],"preferred":["团队管理"],
     "strong":"负责 Java 后端开发，使用 SQL 完成数据查询与数据库设计，并带领团队交付服务接口。",
     "synonym":"长期使用 Spring Boot 构建服务，管理 MySQL 数据库，承担小组代码评审和组员协作。",
     "negative":"没有 Java 开发经验；不熟悉 SQL，主要使用 JavaScript 开发网页界面。",
     "partial":"负责测试接口并整理需求文档，未说明编写过服务端代码或数据库查询。",
     "transfer":"使用 TypeScript 开发 Node.js 接口，熟悉 API 调试流程，暂未使用 Java 技术栈。",
     "unrelated":"从事线下渠道销售，使用办公软件整理客户清单。",
     "stuff":"求职关键词包含 Java、SQL，但相关内容仅来自线上入门课程，无实际项目经历。",
     "hybrid":"使用 JavaScript 和 HTML 开发前端页面，课程中了解 SQL 概念，但未独立开发后端。"},
    {"id":"python_data","title":"Python 数据分析师","required":["Python","SQL"],"preferred":["团队管理"],
     "strong":"使用 Python 处理百万行数据并编写 SQL 分析查询，负责指标体系建设及团队协作。",
     "synonym":"通过 pandas 和 numpy 清洗业务数据，使用 PostgreSQL 做报表汇总，参与小组协作。",
     "negative":"没有 Python 使用经验；不熟悉 SQL，工作只涉及 PowerPoint 排版。",
     "partial":"负责制作 Excel 周报和跟进业务口径，没有描述是否具备编程能力。",
     "transfer":"熟练使用 Excel 透视表与 Power BI 制作看板，尚未涉及程序分析或 SQL。",
     "unrelated":"负责行政接待、采购文具和会议协调。",
     "stuff":"阅读过 Python、SQL 课程介绍，但没有实际使用过这些编程工具。",
     "hybrid":"负责 Excel 数据汇总；了解 Python 的基础概念，未使用 SQL 完成实际工作。"},
    {"id":"finance","title":"总账会计","required":["财务核算"],"preferred":["SQL"],
     "strong":"负责公司财务核算、月末总账和凭证审核，独立完成结账及财务报表。",
     "synonym":"承担总账、往来账务处理和记账凭证复核，使用财务软件完成月度结算。",
     "negative":"未从事财务核算工作，主要负责行政文档和日程管理。",
     "partial":"在财务部门协助整理报销票据，未明确负责总账或核算。",
     "transfer":"曾负责采购付款的材料收集和发票分类，核算由专职会计完成。",
     "unrelated":"担任销售专员，维护客户及跟进订单交付。",
     "stuff":"学习资料列有财务核算、总账、凭证等章节，但尚无会计岗位经历。",
     "hybrid":"负责费用报销单据整理，参加过财务核算课程，未实际承担结账。"},
    {"id":"recruiting","title":"招聘专员","required":["招聘"],"preferred":["团队管理"],
     "strong":"负责招聘渠道维护、候选人简历筛选与面试安排，带领团队完成季度招聘计划。",
     "synonym":"独立开展人才招聘，协调候选人面试及录用流程，参与招聘渠道运营。",
     "negative":"未曾从事招聘工作，也没有面试安排经验，主要负责行政采购。",
     "partial":"支持 HR 部门整理员工档案，未描述是否承担人才招募。",
     "transfer":"参与校园活动组织、嘉宾邀约及日程协调，但没有招聘职责。",
     "unrelated":"做过零售门店的收银和库存统计。",
     "stuff":"培训课程涉及招聘、面试、人才招聘关键词，但本人没有相关实际经验。",
     "hybrid":"参与入职资料准备，了解招聘流程知识，但未负责候选人筛选或面试。"},
    {"id":"inventory","title":"仓储库存主管","required":["库存管理"],"preferred":["SQL"],
     "strong":"负责库存管理、入出库调拨和仓库盘点，推动物料账实核对及库存预警。",
     "synonym":"承担仓储管理、月度盘点、ERP 出入库数据核对和库位优化。",
     "negative":"从未负责库存管理，也没有仓储工作经历，主要进行前台接待。",
     "partial":"负责采购订单沟通，未说明是否参与库存盘点或仓库现场管理。",
     "transfer":"参与销售预测和补货计划，仓库入出库由物流部门管理。",
     "unrelated":"主要进行招聘沟通和候选人面试协调。",
     "stuff":"课程中提到库存管理、ERP、仓储管理，但没有真实仓库项目经历。",
     "hybrid":"负责销售订单跟踪，接受过库存管理培训，但未开展实际盘点。"},
]
NAMES = ['林示例','张演示','陈样本','赵测试','周虚构','王模拟','吴示例','郑演示','许样本','何测试',
         '杨虚构','曹模拟','宋示例','冯演示','朱样本','胡测试','邓虚构','马模拟','郭示例','唐演示']
SCENARIOS = ['direct']*6 + ['paraphrase']*4 + ['explicit_negative']*3 + ['insufficient']*3 + ['transferable']*2 + ['keyword_stuffing'] + ['mixed']
assert len(SCENARIOS)==20
SCENARIO_DESC = {
 'direct':'简历明确陈述必要工作经历', 'paraphrase':'必要经历以同义描述表达',
 'explicit_negative':'明确否认必要经历', 'insufficient':'经历信息不足',
 'transferable':'具备相邻岗位技能，但不能直接证明必要条件',
 'keyword_stuffing':'出现关键词但只是培训或课程内容',
 'mixed':'同时出现部分相关信息和否定性描述'
}


def build_cases():
    jobs=[]; cases=[]
    for ri, role in enumerate(ROLES):
        jobs.append({'id':role['id'],'job_title':role['title'],'jd':f"招聘{role['title']}，必须具备：{'、'.join(role['required'])}。有{'、'.join(role['preferred'])}经验更好。",'required':role['required'],'preferred':role['preferred']})
        for slot, scenario in enumerate(SCENARIOS):
            index=ri*20+slot+1
            code=f'SYN{index:03}'
            name=NAMES[slot]
            claimed=scenario in ('direct','paraphrase')
            block= {'direct':'strong','paraphrase':'synonym','explicit_negative':'negative','insufficient':'partial',
                    'transferable':'transfer','keyword_stuffing':'stuff','mixed':'hybrid'}[scenario]
            years=(3 + (index%7)) if claimed else None
            lines=[name,'【合成测试简历｜完全虚构｜不得用于真实招聘决策】',f'测试编号：{code}',
                   f'应聘方向：{role["title"]}',f'联系邮箱：{code.lower()}@example.invalid',
                   '联系电话：000-0000-0000（无效测试号码）',
                   f'教育经历：示例大学（虚构），{["本科","硕士","大专"][index%3]}，{["工商管理","计算机科学","财务管理","物流管理"][ri%4]}。',
                   '工作经历：', f'{years}年工作经验。' if years else '未提供明确的工作年限。',
                   role[block],
                   '项目经历：',
                   ('负责跨部门项目交付，输出详细工作记录并组织过程复盘。' if claimed else
                    '参与资料归档、会议纪要整理和跨部门信息同步。'),
                   '补充信息：',
                   ('具备较丰富的业务实操经验，具体成果和真实性仍需面试核对。' if claimed else
                    '没有提供足以确认岗位必要条件的独立业务成果。'),
                   '声明：以上姓名、学历、单位、联系方式和经历均由程序生成，无对应真实个人。']
            if slot==4:
                # A common duplicate presentation / colon-label resume pattern.
                lines[0]='姓名：'+name
            if slot==7:
                lines[0]='个人简历'
                lines.insert(1,'姓名：'+name)
            if slot==14:
                lines.insert(6,'技能：Excel、Power BI；谨慎区分工具名称与岗位职责。')
            if slot==18:
                lines.insert(9,'课程关键词不是岗位实践证据，请按上下文核实。')
            text='\n'.join(lines)+'\n'
            cases.append({'id':code,'job_id':role['id'],'synthetic_name':name,'scenario':scenario,
                          'scenario_description':SCENARIO_DESC[scenario], 'human_expected_group':'优先查看' if claimed else '需要确认',
                          'human_required_claimed':claimed,'years_claimed':years,
                          'file':f'{code}_{role["id"]}.txt','text':text})
    return jobs,cases


def _find_font(preferred=None):
    choices=[preferred,os.getenv('HUIYAN_FIXTURE_ZH_FONT'),
             '/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf',
             '/usr/share/fonts/truetype/arphic-gkai00mp/gkai00mp.ttf',
             'C:/Windows/Fonts/simsun.ttc']
    return next((x for x in choices if x and Path(x).exists()),None)


def _find_pil_font(preferred=None):
    choices=[preferred, os.getenv('HUIYAN_FIXTURE_ZH_FONT'),
             '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
             '/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf',
             'C:/Windows/Fonts/msyh.ttc']
    return next((x for x in choices if x and Path(x).exists()),None)


def _to_docx(text,dest):
    from docx import Document
    from docx.shared import Pt
    document=Document()
    lines=text.splitlines()
    document.add_heading('个人简历 · 合成测试数据',0)
    document.add_paragraph(lines[0],style='Subtitle')
    # Use a real Word table to test ordering and cell extraction.
    t=document.add_table(rows=0, cols=2);t.style='Table Grid'
    for line in lines[1:7]:
        row=t.add_row().cells
        k,sep,v=line.partition('：')
        row[0].text=k if sep else '标记';row[1].text=v if sep else line
    document.add_heading('经历与说明',level=1)
    for line in lines[7:]:
        document.add_paragraph(line)
    document.core_properties.author='慧眼合成数据生成器'
    document.core_properties.title='合成简历 - 虚构候选人'
    document.save(dest)


def _to_pdf(text,dest,font):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    if not font: raise RuntimeError('无法找到中文 TTF 字体，请传 --font PATH')
    pdfmetrics.registerFont(TTFont('FixtureChinese',font))
    c=canvas.Canvas(str(dest),pagesize=A4,pageCompression=1,invariant=1)
    c.setTitle('Huiyan synthetic test resume - not a real person')
    width,height=A4
    c.setFont('FixtureChinese',15)
    c.drawString(48,height-60,'慧眼 · 合成测试简历（全部虚构）')
    y=height-98
    for line in text.splitlines():
        wrapped=[line[i:i+45] for i in range(0,len(line),45)] or ['']
        for part in wrapped:
            if y<62:
                c.showPage(); y=height-52
            c.setFont('FixtureChinese',10.4)
            c.drawString(48,y,part)
            y-=18
    c.save()


def _to_scanned_pdf(text,dest,pil_font):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    if not pil_font:raise RuntimeError('未找到 PIL 中文字体，请传 --pil-font PATH')
    img=Image.new('RGB',(1280,1800),'white');draw=ImageDraw.Draw(img)
    font=ImageFont.truetype(pil_font,28)
    big=ImageFont.truetype(pil_font,36)
    draw.text((75,65),'合成测试简历 · 扫描件模拟',font=big,fill=(30,30,30))
    y=140
    for line in text.splitlines():
        for sub in ([line[i:i+33] for i in range(0,len(line),33)] or ['']):
            draw.text((75,y),sub,font=font,fill=(25,25,25));y+=49
            if y>=1700:break
        if y>=1700:break
    img=img.filter(ImageFilter.GaussianBlur(radius=0.35))
    c=canvas.Canvas(str(dest),pagesize=(640,900),invariant=1)
    c.setTitle('Synthetic scanned resume fixture, no text layer')
    c.drawImage(ImageReader(img),0,0,width=640,height=900)
    c.save()


def create(out:Path, include_binary=True, font=None, pil_font=None):
    jobs,cases=build_cases()
    if out.exists() and (out/'META.json').exists():
        shutil.rmtree(out)
    out.mkdir(parents=True,exist_ok=True)
    for sub in ['txt','docx','pdf-text','pdf-scan','zip','invalid']:
        (out/sub).mkdir(exist_ok=True)
    (out/'jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2),encoding='utf-8')
    metadata=[]; stats=Counter()
    font=_find_font(font)
    pil_font=_find_pil_font(pil_font)
    for i,case in enumerate(cases):
        p=(out/'txt'/case['file']);p.write_text(case['text'],encoding='utf-8')
        row={k:v for k,v in case.items() if k!='text'}
        row['variants']=['txt/'+case['file']]
        if include_binary:
            stem=Path(case['file']).stem
            # Every candidate has both editable Word and selectable-text PDF variants.
            target=out/'docx'/(stem+'.docx');_to_docx(case['text'],target)
            row['variants'].append('docx/'+target.name)
            target=out/'pdf-text'/(stem+'.pdf');_to_pdf(case['text'],target,font)
            row['variants'].append('pdf-text/'+target.name)
            if i%10==2: # 12 image-only PDFs for local OCR
                target=out/'pdf-scan'/(stem+'.pdf');_to_scanned_pdf(case['text'],target,pil_font)
                row['variants'].append('pdf-scan/'+target.name)
        metadata.append(row);stats[case['scenario']]+=1
    (out/'truth.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    if include_binary:
        for role in ROLES:
            for sub, ext, tag in (('txt', '.txt', 'text'), ('docx', '.docx', 'word'), ('pdf-text', '.pdf', 'pdf')):
                with zipfile.ZipFile(out/'zip'/f'{role["id"]}-{tag}.zip','w',zipfile.ZIP_DEFLATED) as z:
                    for case in cases:
                        if case['job_id']==role['id']:
                            name = Path(case['file']).with_suffix(ext).name
                            z.write(out/sub/name, name)
        # Separate duplicates for import de-duplication tests.
        first=cases[0]['file'];content=(out/'txt'/first).read_bytes()
        with zipfile.ZipFile(out/'zip'/'duplicate-test.zip','w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('original.txt',content)
            z.writestr('duplicate-different-name.txt',content)
        (out/'invalid'/'empty.txt').write_bytes(b'')
        (out/'invalid'/'corrupt.pdf').write_bytes(b'%PDF-1.7\ncorrupted synthetic test content')
        (out/'invalid'/'not-a-word-file.docx').write_bytes(b'not a docx')
        with zipfile.ZipFile(out/'zip'/'mixed-formats.zip','w',zipfile.ZIP_DEFLATED) as z:
            for folder in ('docx','pdf-text','pdf-scan'):
                for path in sorted((out/folder).iterdir())[:3]:z.write(path,f'{folder}/{path.name}')
    meta={'generator':'Huiyan synthetic benchmark v2','all_data_fictional':True,'candidate_count':len(cases),
          'job_count':len(jobs),'scenario_distribution':dict(stats),'notes':'预期标签为作者设定的合成任务标注，不代表真实招聘准确率。'}
    (out/'META.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'README.md').write_text('''# 慧眼合成测试简历（无真实个人信息）\n\n所有姓名、单位、联系方式、学历、经历及项目均为人工编写模板生成的虚构数据；`example.invalid` 无法接收邮件，`000-0000-0000` 是无效号码。**不得作为真实招聘候选人使用。**\n\n- `jobs.json`：6 类岗位的岗位说明、必要条件与加分条件。\n- `truth.json`：120 位虚构候选人的人工预设标签。`direct` 和 `paraphrase` 应优先复核；`explicit_negative`、`insufficient`、`transferable`、`keyword_stuffing`、`mixed` 属于需人工确认的场景。\n- `txt/`：120 份可直接批量上传的文本简历。\n- `docx/`：120 份包含 Word 表格的简历。\n- `pdf-text/`：120 份有可提取文字层的 PDF 简历。\n- `pdf-scan/`：12 份只有图片、需要 OCR 的 PDF。\n- `zip/`：按岗位、按 PDF/DOCX/TXT 分组的 ZIP，以及混合格式 ZIP 与重复文件 ZIP。\n- `invalid/`：空文档和损坏文档，用于验证失败隔离。\n\n**建议测试方式**：新建一个岗位任务，从 `jobs.json` 复制 JD 和条件，仅导入对应岗位 `txt/` 20 份，观察优先查看/需要确认名单与 `truth.json` 对比。再分开导入 Word、文字 PDF、扫描 PDF 以检查文件兼容性。多个文件格式是同一位候选人的不同表示，请不要把所有格式混在同一真实招聘任务中统计人数。\n\n本数据中的 OCR 文字可能出错，必须回到 PDF 原件人工验证。不要把生成标签当作真实招聘质量评估。\n''',encoding='utf-8')
    return meta


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='testdata/synthetic/generated')
    parser.add_argument('--text-only',action='store_true')
    parser.add_argument('--font',default=None)
    parser.add_argument('--pil-font',default=None)
    args=parser.parse_args()
    meta=create(Path(args.out),not args.text_only,args.font,args.pil_font)
    print(json.dumps(meta,ensure_ascii=False))


if __name__=='__main__':main()
