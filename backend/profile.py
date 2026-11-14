"""Conservative, explainable extraction of non-sensitive resume facts.

No inference of age, gender, health, marital status, or other sensitive traits.
A mention is not a verified credential. All extracted items cite a source page.
"""
from __future__ import annotations

import re

PROFILE_VERSION = 'rules-v1'
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
            # Only explicitly stated years of professional experience; dates alone
            # never imply continuous employment or a minimum tenure.
            matches = re.finditer(r'(?:(\d{1,2})\s*年(?:以上)?(?:相关)?工作经验|(?:相关)?工作经验\s*(\d{1,2})\s*年)', line)
            for match in matches:
                value = int(match.group(1) or match.group(2))
                if 0 < value <= 60:
                    years.append({'years': value, 'evidence': quote})
    # Different statements may conflict; do not choose a "true" duration.
    unique_years = sorted({item['years'] for item in years})
    return {
        'version': PROFILE_VERSION,
        'education_mentions': education[:8],
        'skill_mentions': skills,
        'experience_mentions': experiences,
        'stated_experience_years': unique_years,
        'experience_years_conflict': len(unique_years) > 1,
        'needs_source_review': needs_review,
        'disclaimer': '仅从简历文字提取线索，不代表学历、技能或年限已经核实。',
    }
