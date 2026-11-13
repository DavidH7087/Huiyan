"""Transparent, offline-first evidence retrieval for the phase-one prototype.

NOT a validated employment decision model: every result requires HR review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

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
            if any(normalise(s) in normalise(clause) for s in (canonical, *synonyms)):
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


def find_evidence(term: str, pages: list[dict]) -> dict | None:
    aliases = sorted(alias_options(term), key=len, reverse=True)
    for page in pages:
        original = page.get("text", "")
        normalized = normalise(original)
        for alias in aliases:
            found = normalise(alias)
            if not found or found not in normalized:
                continue
            # Avoid promoting explicitly negative statements to positive evidence.
            # Use the current sentence rather than the entire resume.
            sentences = re.split(r"[。！？!?\n；;]+", original)
            if any(normalise(alias) in normalise(sentence) and _looks_negated(sentence,alias)
                   for sentence in sentences):
                # If ambiguous, err on the side of requiring human verification.
                continue
            # Attempt a readable excerpt centred on the raw alias. Fallback to first text.
            idx = original.lower().find(alias.lower())
            if idx == -1:
                excerpt = original[:180]
            else:
                excerpt = original[max(0, idx - 65):idx + len(alias) + 110]
            excerpt = re.sub(r"\s+", " ", excerpt).strip()
            return {"term": term, "matched_text": alias, "page": page.get("page", 1), "excerpt": excerpt}
    return None


def evaluate(required: list[str], preferred: list[str], pages: list[dict]) -> dict:
    checks=[]
    for term, kind in [(x, "required") for x in required]+[(x, "preferred") for x in preferred]:
        evidence=find_evidence(term,pages)
        checks.append({"term":term,"kind":kind,"state":"有相关文字" if evidence else "待核实","evidence":evidence})
    must=[x for x in checks if x["kind"]=="required"]
    good=[x for x in checks if x["state"]=="有相关文字"]
    required_found=sum(x["state"]=="有相关文字" for x in must)
    # Ratio is an evidence search indicator, not aptitude, probability, or truth.
    total=len(checks)
    coverage=round(len(good)/total*100) if total else 0
    if must and required_found==len(must):
        group="优先查看"
    elif not must and good:
        group="优先查看"
    else:
        group="需要确认"
    return {"group":group,"evidence_coverage":coverage,"checks":checks,
            "matched_count":len(good),"required_met_textually":required_found,
            "sort_key":required_found*10+sum(x["state"]=="有相关文字" for x in checks if x["kind"]=="preferred")}
