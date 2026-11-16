"""Conservative, explainable extraction of non-sensitive resume facts.

No inference of age, gender, health, marital status, or other sensitive traits.
A mention is not a verified credential. All extracted items cite a source page.
"""
from __future__ import annotations

import re

PROFILE_VERSION = 'rules-v3'
DEGREES = ('博士', '硕士', '研究生', '本科', '学士', '大专', '专科')
SKILLS = (
    'Python', 'Java', 'JavaScript', 'TypeScript', 'SQL', 'Excel', 'Power BI',
    'CAD', 'SolidWorks', 'SAP', 'ERP', 'PMP', 'C++', 'C#', 'Photoshop',
)
EXPERIENCE_MARKERS = ('工作经历', '工作经验', '任职', '负责', '项目经历', '项目经验')


def _snippet(line: str) -> str:
    return re.sub(r'\s+', ' ', line).strip()[:240]


def _contains_skill(text: str, skill: str) -> bool:
    return re.search(r'(?<![A-Za-z0-9+#])' + re.escape(skill) + r'(?![A-Za-z0-9+#])', text, re.I) is not None


def _evidence(page: dict, line: str) -> dict:
    return {'page': page.get('page', 1), 'source': page.get('source', 'unknown'),
            'excerpt': _snippet(line), 'needs_verification': page.get('source') == 'ocr'}


def _negated_fact(clause: str, value: str) -> bool:
    """Do not present an explicitly denied qualification as a positive fact."""
    lower = clause.casefold()
    position = lower.find(value.casefold())
    if position < 0:
        return False
    prefix = lower[max(0, position - 24):position]
    suffix = lower[position + len(value):position + len(value) + 12]
    negation = (
        r'(?:没有|从未|未曾|尚无|不具备|缺少|缺乏|'
        r'不熟悉|不会|未使用|没用过|未掌握|未取得|未接触|'
        r'未学习|未完成|未获得|无相关|无)\s*[\w\s]{0,14}
    """Extract only explicitly mentioned facts, storing traceable evidence."""
    education, skills, experiences, years = [], [], [], []
    seen_degrees, seen_skills, seen_experiences = set(), set(), set()
    needs_review = False
    for page in pages:
        if page.get('source') == 'ocr' or page.get('warning'):
            needs_review = True
        for line in (s.strip() for s in page.get('text', '').splitlines()):
            if not line:
                continue
            quote = _evidence(page, line)
            for clause in re.split(r'[，,；;。！!]', line):
                if not clause.strip():
                    continue
                fact_quote = _evidence(page, clause)
                for degree in DEGREES:
                    if degree in clause and degree not in seen_degrees and not _negated_fact(clause, degree) and not _is_requirement(clause, clause.find(degree)):
                        education.append({'label': degree, 'evidence': fact_quote})
                        seen_degrees.add(degree)
                for skill in SKILLS:
                    if (skill.lower() not in seen_skills
                            and _contains_skill(clause, skill)
                            and not _negated_fact(clause, skill)
                            and not _is_requirement(clause, clause.casefold().find(skill.casefold()))):
                        skills.append({'label': skill, 'evidence': fact_quote})
                        seen_skills.add(skill.lower())
            if any(marker in line for marker in EXPERIENCE_MARKERS) and quote['excerpt'] not in seen_experiences:
                if len(experiences) < 12:
                    experiences.append(quote)
                    seen_experiences.add(quote['excerpt'])
            # An explicit skill-specific tenure is not necessarily total employment.
            spans = set()
            patterns = (
                (r'(?<!\d)(\d{1,2})\s*年(?:以上|左右|多)?(?:的)?\s*(?:相关)?工作经验', 'total'),
                (r'(?:相关)?工作经验\s*(\d{1,2})\s*年', 'total'),
                (r'(?<!\d)(\d{1,2})\s*年(?:以上|左右|多)?[^。；;，,\n]{0,36}?(?:经验|经历)', 'specific'),
            )
            for expression, scope in patterns:
                for match in re.finditer(expression, line):
                    value = int(match.group(1))
                    if not 0 < value <= 60:
                        continue
                    span = (match.start(), match.end())
                    if scope == 'specific' and any(
                            start <= span[0] and end >= span[1]
                            for start, end in spans):
                        continue
                    if _is_requirement(line, match.start()):
                        continue
                    if scope == 'specific' and not any(x in match.group(0) for x in
                            ('销售','客户','开发','管理','工作','项目','技术','招聘',
                             '财务','运营','设计','采购','市场','产品','服务','经验')):
                        continue
                    years.append({'years':value,'scope':scope,'evidence':quote,
                                  'context':_snippet(match.group(0))})
                    spans.add(span)
    # Different statements may conflict; do not choose a "true" duration.
    unique_years = sorted({item['years'] for item in years})
    return {
        'version': PROFILE_VERSION,
        'education_mentions': education[:8],
        'skill_mentions': skills,
        'experience_mentions': experiences,
        'stated_experience_years': unique_years,
        'experience_duration_mentions': years,
        'experience_years_conflict': len({item['years'] for item in years if item['scope'] == 'total'}) > 1,
        'needs_source_review': needs_review,
        'disclaimer': '仅从简历文字提取线索，不代表学历、技能或年限已经核实。',
    }

    )
    return bool(re.search(negation, prefix, re.I)) or bool(
        re.match(r'(?:学历)?(?:未毕业|未取得|肄业)', suffix)
    )


def _is_requirement(line: str, offset: int) -> bool:
    """A requested qualification in a résumé is not possessed experience."""
    prefix = line[max(0, offset - 26):offset]
    return bool(re.search(
        r'(?:岗位要求|职位要求|招聘要求|任职要求|申请要求|'
        r'至少需要|要求至少|需要至少|需要有|必须有|须有|'
        r'没有|未有|不具备|不足|缺少|没有达到|尚未达到)'
        r'[^。；;，,\n]{0,14}
    """Extract only explicitly mentioned facts, storing traceable evidence."""
    education, skills, experiences, years = [], [], [], []
    seen_degrees, seen_skills, seen_experiences = set(), set(), set()
    needs_review = False
    for page in pages:
        if page.get('source') == 'ocr' or page.get('warning'):
            needs_review = True
        for line in (s.strip() for s in page.get('text', '').splitlines()):
            if not line:
                continue
            quote = _evidence(page, line)
            for degree in DEGREES:
                if degree in line and degree not in seen_degrees:
                    education.append({'label': degree, 'evidence': quote})
                    seen_degrees.add(degree)
            for skill in SKILLS:
                if skill.lower() not in seen_skills and _contains_skill(line, skill):
                    skills.append({'label': skill, 'evidence': quote})
                    seen_skills.add(skill.lower())
            if any(marker in line for marker in EXPERIENCE_MARKERS) and quote['excerpt'] not in seen_experiences:
                if len(experiences) < 12:
                    experiences.append(quote)
                    seen_experiences.add(quote['excerpt'])
            # An explicit skill-specific tenure is not necessarily total employment.
            spans = set()
            patterns = (
                (r'(?<!\d)(\d{1,2})\s*年(?:以上|左右|多)?(?:相关)?工作经验', 'total'),
                (r'(?:相关)?工作经验\s*(\d{1,2})\s*年', 'total'),
                (r'(?<!\d)(\d{1,2})\s*年(?:以上|左右|多)?[^。；;，,\n]{0,36}?(?:经验|经历)', 'specific'),
            )
            for expression, scope in patterns:
                for match in re.finditer(expression, line):
                    value = int(match.group(1))
                    if not 0 < value <= 60:
                        continue
                    span = (match.start(), match.end())
                    if scope == 'specific' and any(
                            start <= span[0] and end >= span[1]
                            for start, end in spans):
                        continue
                    prefix = line[max(0, match.start()-12):match.start()]
                    if re.search(r'(?:没有|未有|不具备|不足|缺少|要求至少|须有)$', prefix):
                        continue
                    if scope == 'specific' and not any(x in match.group(0) for x in
                            ('销售','客户','开发','管理','工作','项目','技术','招聘',
                             '财务','运营','设计','采购','市场','产品','服务','经验')):
                        continue
                    years.append({'years':value,'scope':scope,'evidence':quote})
                    spans.add(span)
    # Different statements may conflict; do not choose a "true" duration.
    unique_years = sorted({item['years'] for item in years})
    return {
        'version': PROFILE_VERSION,
        'education_mentions': education[:8],
        'skill_mentions': skills,
        'experience_mentions': experiences,
        'stated_experience_years': unique_years,
        'experience_duration_mentions': years,
        'experience_years_conflict': len(unique_years) > 1,
        'needs_source_review': needs_review,
        'disclaimer': '仅从简历文字提取线索，不代表学历、技能或年限已经核实。',
    }
, prefix
    ))


def extract_profile(pages: list[dict]) -> dict:
    """Extract only explicitly mentioned facts, storing traceable evidence."""
    education, skills, experiences, years = [], [], [], []
    seen_degrees, seen_skills, seen_experiences = set(), set(), set()
    needs_review = False
    for page in pages:
        if page.get('source') == 'ocr' or page.get('warning'):
            needs_review = True
        for line in (s.strip() for s in page.get('text', '').splitlines()):
            if not line:
                continue
            quote = _evidence(page, line)
            for degree in DEGREES:
                if degree in line and degree not in seen_degrees:
                    education.append({'label': degree, 'evidence': quote})
                    seen_degrees.add(degree)
            for skill in SKILLS:
                if skill.lower() not in seen_skills and _contains_skill(line, skill):
                    skills.append({'label': skill, 'evidence': quote})
                    seen_skills.add(skill.lower())
            if any(marker in line for marker in EXPERIENCE_MARKERS) and quote['excerpt'] not in seen_experiences:
                if len(experiences) < 12:
                    experiences.append(quote)
                    seen_experiences.add(quote['excerpt'])
            # An explicit skill-specific tenure is not necessarily total employment.
            spans = set()
            patterns = (
                (r'(?<!\d)(\d{1,2})\s*年(?:以上|左右|多)?(?:相关)?工作经验', 'total'),
                (r'(?:相关)?工作经验\s*(\d{1,2})\s*年', 'total'),
                (r'(?<!\d)(\d{1,2})\s*年(?:以上|左右|多)?[^。；;，,\n]{0,36}?(?:经验|经历)', 'specific'),
            )
            for expression, scope in patterns:
                for match in re.finditer(expression, line):
                    value = int(match.group(1))
                    if not 0 < value <= 60:
                        continue
                    span = (match.start(), match.end())
                    if scope == 'specific' and any(
                            start <= span[0] and end >= span[1]
                            for start, end in spans):
                        continue
                    prefix = line[max(0, match.start()-12):match.start()]
                    if re.search(r'(?:没有|未有|不具备|不足|缺少|要求至少|须有)$', prefix):
                        continue
                    if scope == 'specific' and not any(x in match.group(0) for x in
                            ('销售','客户','开发','管理','工作','项目','技术','招聘',
                             '财务','运营','设计','采购','市场','产品','服务','经验')):
                        continue
                    years.append({'years':value,'scope':scope,'evidence':quote})
                    spans.add(span)
    # Different statements may conflict; do not choose a "true" duration.
    unique_years = sorted({item['years'] for item in years})
    return {
        'version': PROFILE_VERSION,
        'education_mentions': education[:8],
        'skill_mentions': skills,
        'experience_mentions': experiences,
        'stated_experience_years': unique_years,
        'experience_duration_mentions': years,
        'experience_years_conflict': len(unique_years) > 1,
        'needs_source_review': needs_review,
        'disclaimer': '仅从简历文字提取线索，不代表学历、技能或年限已经核实。',
    }
