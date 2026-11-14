"""Conservative context guards for evidence-based résumé retrieval.

Keyword mentions in course listings, negated experience statements and
hypothetical/uncertain duties should not be treated as job-experience evidence.
This is not a semantic classifier or a qualification assessment.
"""
from __future__ import annotations

import re

# These cues apply only to a clause containing the matched term.  Do not reject
# separate, explicit work-history evidence merely because a CV also mentions
# courses or an unrelated limitation elsewhere.
NEGATIVE = (
    '没有', '没做过', '未曾', '未从事', '从未', '不具备', '不熟悉',
    '缺少', '缺乏', '尚无', '尚未', '未涉及', '无相关',
    '未负责', '没有负责', '未使用', '没用过', '未实际', '没有实际',
    '未独立', '不承担', '并未', '未开展', '暂未', '从未负责',
)
UNCERTAIN = (
    '未说明', '未描述', '未明确', '无法确认', '不确定',
    '是否承担', '是否具备', '尚不清楚', '不能证明',
)
TRAINING = (
    '培训', '课程', '教学', '讲座', '教材', '学习资料', '课程大纲',
    '线上入门', '理论知识', '基础概念', '自学', '学习过',
    '阅读过', '了解', '关键词', '仅听过', '只听过', '课堂',
)
PRACTICE = (
    '独立负责', '独立承担', '工作中使用', '实际使用', '实战',
    '开发过', '项目中使用', '项目经验', '上线', '交付',
    '负责', '搭建', '实现', '实施', '管理', '维护',
)


def _canonical(text: str) -> str:
    return re.sub(r'[\s\-_/（）()\[\]·]+', '', text).lower()


def rejection_reason(sentence: str, alias: str) -> str | None:
    """Explain why this mention is unsafe as a positive experience signal.

    We intentionally prefer false uncertainty to a falsely positive shortlist.
    The separate full sentence is returned for human review, not thrown away.
    """
    # Target roles, résumé titles and synthetic-data disclaimers describe the
    # document, not demonstrated capabilities. A title may itself be a job name.
    heading = sentence.strip()
    if re.match(r'^(?:应聘方向|求职意向|求职岗位|目标岗位|意向岗位|期望职位|应聘职位|应聘岗位|目标职位|简历标题)\s*[：:]', heading):
        return '仅在求职意向中出现'
    if any(phrase in heading for phrase in ('合成测试简历', '不得用于真实招聘决策', '虚构测试数据仅供')):
        return '简历标识或测试声明'
    text = _canonical(sentence)
    token = _canonical(alias)
    index = text.find(token)
    if index < 0:
        # Latin tokens may be delimited in a way not preserved by normalization.
        return None
    # Negations sometimes appear after the keyword, as in
    # 'Java：未从事相关开发'. A relatively short scope limits unrelated clauses.
    prefix = text[max(0, index - 28):index]
    suffix = text[index + len(token): index + len(token) + 50]
    # '从未负责库存管理', '没有 SQL 开发经验', '不承担客户开发'
    if any(marker in prefix for marker in NEGATIVE):
        return '明确否定或未承担相关工作'
    if any(marker in suffix for marker in NEGATIVE):
        return '明确否定或未承担相关工作'
    if any(marker in prefix for marker in UNCERTAIN) or any(marker in suffix for marker in UNCERTAIN):
        return '未明确说明是否承担相关职责'
    # A term surrounded by training or curriculum is not proof of practice.
    # A later clause with explicit practical experience is independently checked.
    training_before = any(word in prefix for word in TRAINING)
    training_after = any(word in suffix[:28] for word in ('培训', '课程', '理论', '学习'))
    if training_before or training_after:
        if not any(word in prefix + suffix[:22] for word in PRACTICE):
            return '仅在课程或培训语境中出现'
    return None
