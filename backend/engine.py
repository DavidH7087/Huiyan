"""Transparent, offline-first evidence retrieval for the phase-one prototype.

NOT a validated employment decision model: every result requires HR review.
"""
from __future__ import annotations

import re
from .evidence_context import rejection_reason

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


def suggest_conditions(description: str) -> dict:
    """Small deterministic convenience parser; the UI requires human confirmation."""
    required: list[str] = []
    preferred: list[str] = []
    clauses = re.split(r"[。；;\n，,]+", description or "")
    for raw in clauses:
        clause = raw.strip()
        if not clause:
            continue
        if any(x in clause for x in ("不限于", "不要求", "不限制", "无需")):
            continue
        is_preferred = any(x in clause for x in ("最好", "优先", "加分", "更好", "期望"))
        for canonical, synonyms in ALIASES.items():
            if any(_contains_alias(clause, synonym) for synonym in (canonical, *synonyms)):
                target = preferred if is_preferred else required
                if canonical not in target:
                    target.append(canonical)
    # '最好有制造业...不限定润滑油行业' can leave an unwanted must
    required = [x for x in required if x not in preferred]
    return {"required": required, "preferred": preferred, "disclaimer": "自动识别仅提供初稿，请核实并修改条件后再筛选。"}


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
    # Exact mode disables synonym expansion; it still normalises whitespace/case.
    aliases = sorted(([term] if match_mode == 'exact' else alias_options(term)), key=len, reverse=True)
    for page in pages:
        original = page.get("text", "")
        sentences = re.split(r"[。！？!?\n；;]+", original)
        for sentence in sentences:
            if not sentence.strip():
                continue
            for alias in aliases:
                if (not _contains_alias(sentence, alias) or _looks_negated(sentence, alias)
                        or rejection_reason(sentence, alias)):
                    continue
                idx = sentence.lower().find(alias.lower())
                excerpt=(sentence[max(0,idx-70):idx+len(alias)+140] if idx>=0 else sentence[:220])
                excerpt=re.sub(r"\s+", " ", excerpt).strip()
                return {"term": term, "matched_text": alias, "page": page.get("page", 1), "excerpt": excerpt, "source": page.get("source", "text")}
    return None


def evaluate(required: list[str], preferred: list[str], pages: list[dict], semantic_matcher=None,
             excluded: list[str] | None = None, match_mode: str = 'aliases') -> dict:
    checks=[]
    excluded=excluded or []
    for term, kind in [(x, "required") for x in required]+[(x, "preferred") for x in preferred]:
        evidence=find_evidence(term,pages,match_mode)
        checks.append({"term":term,"kind":kind,"state":("OCR文字待核实" if evidence and evidence.get("source")=="ocr" else "有相关文字" if evidence else "待核实"),
                       "evidence":evidence,"semantic_hint":None})
    # Exclusion evidence is a manual verification signal, never a deletion rule.
    for term in excluded:
        evidence=find_evidence(term,pages,match_mode)
        checks.append({'term':term,'kind':'excluded',
                       'state':('OCR排除线索待核实' if evidence and evidence.get('source')=='ocr'
                                else '排除线索待人工核实' if evidence else '未发现排除线索'),
                       'evidence':evidence,'semantic_hint':None})
    if semantic_matcher is not None:
        missing = [c['term'] for c in checks if c['kind']!='excluded' and not c['evidence']]
        hints = semantic_matcher.search_many(missing, pages) if missing else {}
        for check in checks:
            if not check['evidence'] and check['term'] in hints:
                check['semantic_hint'] = hints[check['term']]
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
