"""Transparent, offline-first evidence retrieval for the phase-one prototype.

NOT a validated employment decision model: every result requires HR review.
"""
from __future__ import annotations

import re
from .evidence_context import TRAINING, rejection_reason

# The vocabulary improves recall for a small starter set of Chinese job descriptions.
# It is not a complete occupational ontology or a semantic language model.
ALIASES: dict[str, tuple[str, ...]] = {
    "B2B销售": ("B2B", "企业销售", "对公销售", "工业品销售", "企业级销售", "企业客户销售", "工厂销售", "商务拓展"),
    "客户开发": ("客户开发", "开发客户", "新客户", "陌拜", "客户拓展", "开发企业客户", "开发制造企业", "客户拜访", "拓客"),
    "制造业": ("制造业", "制造企业", "工厂", "工业客户", "生产企业", "生产制造"),
    "大客户管理": ("大客户", "KA客户", "重点客户", "战略客户", "客户关系管理"),
    "渠道拓展": ("渠道开发", "渠道拓展", "经销商开发", "代理商开发", "分销网络", "渠道建设"),
    "Python": ("python", "pandas", "numpy"),
    "Java": ("java", "spring boot", "springboot"),
    "SQL": ("sql", "mysql", "postgresql", "sql server"),
    "财务核算": ("财务核算", "总账", "账务处理", "凭证", "财务报表"),
    "招聘": ("招聘", "人才招聘", "候选人面试", "招聘渠道"),
    "库存管理": ("库存管理", "盘点", "出入库", "仓储管理", "erp"),
    "团队管理": ("团队管理", "管理团队", "带领团队", "下属管理", "部门负责人"),
}


def normalise(value: str) -> str:
    return re.sub(r"[\s\-_/（）()\[\]·]+", "", value or "").lower()


def split_terms(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        values = value
    else:
        values = re.split(r"[,，、;；\n]+", value or "")
    return list(dict.fromkeys(x.strip() for x in values if x and x.strip()))


def alias_options(term: str) -> list[str]:
    clean = normalise(term)
    matches = [term]
    for canonical, synonyms in ALIASES.items():
        all_terms = (canonical, *synonyms)
        if clean in {normalise(x) for x in all_terms}:
            matches = list(all_terms)
            break
    return list(dict.fromkeys(matches))


def _is_recruiting_skill(clause: str) -> bool:
    """Distinguish 'we are recruiting a salesperson' from hiring expertise."""
    return bool(re.search(
        r"(?:负责|从事|主导|组织|参与|具备|拥有|熟悉|开展).{0,8}招聘"
        r"|招聘(?:专员|经理|经验|工作|渠道|流程|管理|项目|体系)"
        r"|(?:校园|社会|人才|员工|人员)招聘|人力资源招聘",
        clause, re.I))


def _known_skills(clause: str) -> list[str]:
    found = []
    for canonical, aliases in ALIASES.items():
        if canonical == "招聘" and not _is_recruiting_skill(clause):
            continue
        if any(_contains_alias(clause, alias) for alias in (canonical, *aliases)):
            found.append(canonical)
    return found


def _clean_requirement_clause(raw: str) -> str:
    part = re.sub(r"【[^】]{0,60}】|（(?:功能|合成)?测试）", "", raw).strip()
    # Strip JD instructions; never turn '招聘' itself into a skill.
    for _ in range(5):
        changed = re.sub(
            r"^(?:本岗位|岗位要求|岗位描述|职位要求|任职要求|现|正在|计划|拟|招聘|招募|"
            r"希望|寻找|需要|必须|优先|考虑|最好|最好有|优先考虑|最好熟悉|"
            r"具有|具备|拥有|有|熟悉|掌握|擅长|能够|可以|独立|相关|并且|和|及|的)\s*",
            "", part).strip(" ：:")
        if changed == part:
            break
        part = changed
    part = re.sub(
        r"(?:的候选人|的应聘者|的人选|相关工作经验|工作经验|相关经验|经验|能力|经历|背景|方面)$",
        "", part).strip()
    return part


def suggest_conditions(description: str) -> dict:
    """Suggest candidate skills, excluding hiring instructions and disclaimers."""
    required: list[str] = []
    preferred: list[str] = []
    clauses = re.split(r"[。；;\n，,、]+", description or "")
    for raw in clauses:
        clause = re.sub(r"【[^】]{0,60}】", "", raw).strip()
        if not clause or any(x in clause for x in ("不限于", "不要求", "不限制", "无需", "不考虑")):
            continue
        is_preferred = any(x in clause for x in ("最好", "优先", "加分", "更好", "期望"))
        for canonical in _known_skills(clause):
            target = preferred if is_preferred else required
            if canonical not in target:
                target.append(canonical)
    required = [x for x in required if x not in preferred]
    return {"required": required, "preferred": preferred,
            "disclaimer": "自动识别仅提供初稿，请核实并修改条件后再筛选。"}


def _condition_key(term: str) -> str:
    """Deduplicate human terms against cleaned description/synonym variants."""
    plain = _clean_requirement_clause(term)
    matches = _known_skills(plain)
    if len(matches) == 1:
        return normalise(matches[0])
    return normalise(plain or term)


def dedupe_conditions(required: list[str], preferred: list[str]) -> tuple[list[str], list[str]]:
    """A required term wins over a duplicate optional clue; never double score."""
    seen = set()
    outputs = ([], [])
    for source, target in ((required, outputs[0]), (preferred, outputs[1])):
        for term in source:
            term = term.strip()
            key = _condition_key(term)
            if term and key and key not in seen:
                target.append(term)
                seen.add(key)
    return outputs


def expand_description_leads(leads: list[str]) -> list[str]:
    """Normalise legacy prompts to atomic skills without mutating stored history."""
    out: list[str] = []
    for clue in leads:
        cleaned = _clean_requirement_clause(clue)
        if not cleaned:
            continue
        matched = _known_skills(cleaned)
        out.extend(matched or [cleaned])
    return dedupe_conditions([], out)[1]


def _looks_negated(source: str, alias: str) -> bool:
    """Conservative shortcut: negative mentions cannot be counted as positive evidence.

    This is not general Chinese negation understanding and may miss complex cases.
    """
    text = normalise(source)
    token = normalise(alias)
    for marker in ("没有", "未曾", "不具备", "缺少", "尚无", "未涉及", "不熟悉", "无相关", "未从事"):
        if re.search(re.escape(marker) + r".{0,16}" + re.escape(token), text):
            return True
        if re.search(re.escape(token) + r".{0,12}" + re.escape(marker), text):
            return True
    return False


def _contains_alias(text: str, alias: str) -> bool:
    token=normalise(alias)
    if not token:
        return False
    # Keep word boundaries: Java must not match JavaScript.
    if re.fullmatch(r'[a-z0-9\s]+', alias.strip().lower()):
        pattern=r'(?<![a-z0-9])'+r'\s*'.join(re.escape(part) for part in alias.lower().split())+r'(?![a-z0-9])'
        return re.search(pattern,text.lower()) is not None
    return token in normalise(text)


def find_evidence(term: str, pages: list[dict], match_mode: str = 'aliases') -> dict | None:
    # Exact disables synonym expansion but still normalises case/whitespace.
    aliases = sorted(([term] if match_mode == 'exact' else alias_options(term)), key=len, reverse=True)
    for page in pages:
        original = page.get("text", "")
        sentences = re.split(r"[。！？!?\n；;]+", original)
        for sentence in sentences:
            if not sentence.strip():
                continue
            # Context across comma-separated keyword lists matters: '课程中提到
            # 库存管理、ERP' is training, not work experience. Conversely, a '没有'
            # in the next clause cannot negate an unrelated preceding skill.
            strong_practice = ('独立负责', '独立承担', '工作中使用', '实际使用',
                               '实战', '开发过', '项目中使用', '项目经验',
                               '上线', '交付', '负责', '搭建', '实现', '实施')
            training_only = (any(word in sentence for word in TRAINING)
                             and not any(word in sentence for word in strong_practice))
            if training_only:
                continue
            clauses = re.split(r"[，,]+", sentence)
            for clause in clauses:
                if not clause.strip():
                    continue
                for alias in aliases:
                    if (not _contains_alias(clause, alias)
                            or _looks_negated(clause, alias)
                            or rejection_reason(clause, alias)):
                        continue
                    idx = clause.lower().find(alias.lower())
                    excerpt = (clause[max(0, idx-70):idx+len(alias)+140]
                               if idx >= 0 else clause[:220])
                    excerpt = re.sub(r"\s+", " ", excerpt).strip()
                    return {"term": term, "matched_text": alias, "page": page.get("page", 1),
                            "excerpt": excerpt, "source": page.get("source", "text")}
    return None


def description_clues(description: str, limit: int = 8) -> list[str]:
    """Extract atomic optional clues, avoiding redundant instruction phrases."""
    if not description or not description.strip():
        return []
    out: list[str] = []
    for raw in re.split(r"[。！？!?；;\n，,、]+", description):
        clause = re.sub(r"【[^】]{0,60}】", "", raw).strip()
        if not clause or any(x in clause for x in ("不要求", "无需", "不限", "不限制", "不考虑")):
            continue
        skills = _known_skills(clause)
        candidate = skills or [_clean_requirement_clause(clause)]
        for term in candidate:
            if 2 <= len(term) <= 30 and term not in ("人选", "人才", "经验", "能力", "工作", "岗位"):
                out.append(term)
        if len(out) >= limit:
            break
    return dedupe_conditions([], out)[1][:limit]


def _negative_semantic_excerpt(term: str, excerpt: str) -> bool:
    """A denial must never be promoted into a positive dense-retrieval lead."""
    # A semantic passage has no clause-level proof; when an experience denial
    # appears, prefer conservative uncertainty over a false positive.
    denial = ("没有", "没做过", "未曾", "未从事", "从未", "不具备",
              "缺少", "缺乏", "尚无", "未涉及", "无相关", "未负责",
              "无", "不熟悉", "未实际", "未独立", "不承担")
    return any(marker in excerpt for marker in denial)


def _offtopic_semantic_excerpt(term: str, excerpt: str) -> bool:
    """Stop technical '开发' from looking like business customer acquisition."""
    canonical = _condition_key(term)
    if canonical == normalise("客户开发") or ("客户" in term and ("开发" in term or "拓展" in term)):
        anchors = ("客户", "销售", "商务", "市场", "拓客", "渠道", "采购",
                   "经销", "销售商", "分销", "企业业务", "B2B")
        return not any(word.lower() in excerpt.lower() for word in anchors)
    if canonical == normalise("B2B销售"):
        return not any(word.lower() in excerpt.lower() for word in
                       ("客户", "销售", "采购", "商务", "市场", "经销", "渠道", "B2B"))
    return False


def evaluate(required: list[str], preferred: list[str], pages: list[dict], semantic_matcher=None,
             excluded: list[str] | None = None, match_mode: str = 'aliases',
             term_modes: dict[str,str] | None = None) -> dict:
    required, preferred = dedupe_conditions(required, preferred)
    checks=[]
    excluded=excluded or []
    for term, kind in [(x, "required") for x in required]+[(x, "preferred") for x in preferred]:
        evidence=find_evidence(term,pages,(term_modes or {}).get(term,match_mode))
        checks.append({"term":term,"kind":kind,"state":("OCR文字待核实" if evidence and evidence.get("source")=="ocr" else "有相关文字" if evidence else "待核实"),
                       "evidence":evidence,"semantic_hint":None})
    # Exclusion evidence is a manual verification signal, never a deletion rule.
    for term in excluded:
        evidence=find_evidence(term,pages,(term_modes or {}).get(term,match_mode))
        checks.append({'term':term,'kind':'excluded',
                       'state':('OCR排除线索待核实' if evidence and evidence.get('source')=='ocr'
                                else '排除线索待人工核实' if evidence else '未发现排除线索'),
                       'evidence':evidence,'semantic_hint':None})
    if semantic_matcher is not None:
        missing = [c['term'] for c in checks if c['kind']!='excluded' and not c['evidence']]
        hints = semantic_matcher.search_many(missing, pages) if missing else {}
        for check in checks:
            if check['kind']=='excluded' or check['evidence'] or check['term'] not in hints:
                continue
            hint = hints[check['term']]
            excerpt = str(hint.get('excerpt', ''))
            if _negative_semantic_excerpt(check['term'], excerpt):
                check['negative_evidence'] = hint
                check['state'] = '明确否定表述待核实'
                continue
            if _offtopic_semantic_excerpt(check['term'], excerpt):
                # A generic shared word ('开发') is not a recruiting lead.
                continue
            check['semantic_hint'] = hint
            check['state'] = '语义相关待核实'

    positive_checks=[x for x in checks if x['kind']!='excluded']
    must=[x for x in positive_checks if x['kind']=='required']
    good=[x for x in positive_checks if x['state']=='有相关文字']
    exclusion_flags=sum(bool(x['evidence']) for x in checks if x['kind']=='excluded')
    required_found=sum(x["state"]=="有相关文字" for x in must)
    # Ratio is an evidence search indicator, not aptitude, probability, or truth.
    total=len(positive_checks)
    coverage=round(sum(bool(c['evidence']) for c in positive_checks)/total*100) if total else 0
    if must and required_found==len(must):
        group="优先查看"
    elif not must and good:
        group="优先查看"
    else:
        group="需要确认"
    if exclusion_flags:
        group='需要确认'
    hint_count=sum(bool(c['semantic_hint']) for c in positive_checks)
    return {'group':group,'evidence_coverage':coverage,'checks':checks,
            'matched_count':sum(bool(c['evidence']) for c in positive_checks),
            'required_met_textually':required_found,
            'semantic_hint_count':hint_count,'exclusion_flags':exclusion_flags,
            'sort_key':(required_found*10+sum(x['state']=='有相关文字'
                          for x in positive_checks if x['kind']=='preferred')
                        +min(hint_count,5)*0.01 - exclusion_flags*100)}
