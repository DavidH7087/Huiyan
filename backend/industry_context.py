"""Conservative, explainable industry evidence grouped by résumé section.

A degree or a classroom mention is NOT counted as industry work experience.
This is a small, auditable vocabulary, not occupational verification.
"""
from __future__ import annotations

import re

_SECTION_HEADERS = {
    'work': ('工作经历','实习经历','职业经历','任职经历','实习经验','工作履历','工作经验'),
    'project': ('项目经历','项目经验','个人项目','科研项目'),
    'education': ('教育背景','教育经历','学历背景','学习经历'),
}
_OTHER_HEADERS = ('专业技能','IT技能','技能特长','主修课程','课程','语言能力',
                  '个人介绍','自我评价','兴趣爱好','获奖荣誉','求职意向')
_TECH = re.compile(
    r'自动驾驶|无人车|无人驾驶|智能驾驶|智能网联|汽车电子|'
    r'机器人|嵌入式|传感器|计算机科学|计算机专业|计算机视觉|人工智能|机器学习|'
    r'软件开发|软件工程|信息技术|互联网|数据库|云计算|'
    r'数据平台|科技|研发|算法|芯片|微电子|'
    r'(?<![a-z])IT(?![a-z])|(?<![a-z])AI(?![a-z])|'
    r'Python|JavaScript|MicroBit',
    re.I
)
_TECH_STRONG = re.compile(
    r'自动驾驶|无人车|无人驾驶|智能驾驶|智能网联|机器人|嵌入式|'
    r'计算机视觉|人工智能|软件开发|信息技术|科技公司|科技有限|'
    r'(?<![a-z])IT\s*实习|(?<![a-z])AI(?![a-z])',
    re.I
)
_COMPANY_ROLE = re.compile(
    r'实习|任职|工程师|设计师|开发人员|产品经理|'
    r'负责|参与|开展|经理|公司|集团|研究院|'
    r'(?<![a-z])IT(?![a-z])',
    re.I
)
_NEW_JOB = re.compile(
    r'^(?:(?:19|20)\d{2}[./年-]|[\u3400-\u9fffA-Za-z]{2,30}(?:公司|集团|研究院)).{0,85}'
)
_NEGATIVE = ('没有','未曾','从未','缺乏','不具备','未从事','尚无','无相关','未参与')
_REQUIREMENTS = ('岗位要求','职位要求','招聘要求','任职要求','求职意向')


def is_technology_experience(term: str) -> bool:
    text = re.sub(r'[\s、，,的]+', '', term).lower()
    return bool(re.search(
        r'(?:科技|高科技|技术|互联网|软件|信息技术|人工智能|数字技术)'
        r'(?:行业|领域|企业|公司)?(?:经验|经历|背景|从业|实习|工作)'
        r'|(?:科技|高科技|技术|互联网|信息技术)(?:行业|领域|企业|公司)',
        text
    ))


def _heading(text: str) -> str | None:
    clean = text.strip(' ：:|｜•·#\t ')
    for section, names in _SECTION_HEADERS.items():
        if clean in names:
            return section
    if clean in _OTHER_HEADERS:
        return 'other'
    return None


def _relevant_work(text: str) -> bool:
    if not _TECH.search(text) or not _COMPANY_ROLE.search(text):
        return False
    # A sidebar skill list is not work experience without a described role.
    if not (_NEW_JOB.match(text) or re.search(
            r'(?:实习|任职|入职|工作中|工作经历|负责|参与|在.{1,20}公司)',text)):
        return False
    if any(x in text for x in _REQUIREMENTS):
        return False
    # For short negative-only entries, do not present a claimed absence as work.
    if any(text.strip().startswith(x) for x in _NEGATIVE):
        return False
    return True


def section_passages(pages: list[dict], max_entries: int = 96) -> list[dict]:
    """Combine job headings with duties so short fragmented CV lines retain context."""
    entries: list[dict] = []
    section = 'other'
    buffer: list[str] = []
    start_page = 1
    start_source = 'text'

    def flush():
        nonlocal buffer
        if buffer:
            excerpt = '；'.join(buffer)[:450].strip()
            if excerpt:
                entries.append({'page': start_page, 'source': start_source,
                                'excerpt': excerpt, 'section': section})
        buffer = []

    for page in pages[:120]:
        for raw in str(page.get('text','')).splitlines():
            line = re.sub(r'\s+', ' ', raw).strip(' \t•-')
            if not line:
                continue
            heading = _heading(line)
            if heading is not None:
                flush()
                # Two-column Word CVs can insert a sidebar such as "IT技能"
                # between one internship and the next. Don't lose the work
                # section merely because the sidebar heading was flattened.
                sidebar = heading=='other' and line in (
                    'IT技能','专业技能','技能特长','主修课程','语言能力','获奖荣誉')
                if not (section=='work' and sidebar):
                    section = heading
                if len(entries) >= max_entries:
                    return entries[:max_entries]
                continue
            if section not in ('work','project','education'):
                continue
            if (section == 'work' and buffer and _NEW_JOB.search(line)
                    and (re.search(r'公司|实习|集团|研究院|任职|工程师',line))):
                flush()
            if not buffer:
                start_page=page.get('page',1)
                start_source=page.get('source','text')
            if len(buffer)<9:
                buffer.append(line[:240])
            if len(entries) >= max_entries:
                return entries[:max_entries]
    flush()
    return entries[:max_entries]


def industry_evidence(term: str, pages: list[dict], limit: int = 3) -> dict[str,list[dict]]:
    """Return WORK evidence first and separate educational/project context.

    Work entries with an identifiable technology domain are supporting text,
    not a verified qualification or an automatic hiring decision.
    """
    if not is_technology_experience(term):
        return {'work': [], 'background': []}
    work: list[dict] = []
    background: list[dict] = []
    seen = set()
    for entry in section_passages(pages):
        excerpt=entry['excerpt']
        if not _TECH.search(excerpt):
            continue
        if any(x in excerpt for x in _REQUIREMENTS):
            continue
        category=entry['section']
        if category=='work':
            if not _relevant_work(excerpt):
                continue
            item={**entry, 'basis':'行业经历','review_required':True}
            target=work
        elif category in ('project','education'):
            item={**entry,'basis':'项目背景' if category=='project' else '教育背景',
                  'review_required':True}
            target=background
        else:
            continue
        key=re.sub(r'\s+', '', excerpt[:110]).lower()
        if key in seen:
            continue
        seen.add(key)
        target.append(item)
    def relevance(item: dict) -> tuple[int,int]:
        text=item['excerpt']
        return (int(bool(_TECH_STRONG.search(text)))*3+len(set(_TECH.findall(text))),
                int(bool(re.search(r'负责|参与|研发|设计|开发|落地',text))))
    work.sort(key=relevance,reverse=True)
    background.sort(key=lambda x:(x['section']!='project',-len(x['excerpt'])))
    return {'work':work[:limit], 'background':background[:3]}
