"""Non-destructive cross-format duplicate hints for a single recruitment task.

Only exact normalized email or validated mobile matches create hints. Names
alone must never trigger a merge. All original files and review decisions stay.
"""
from __future__ import annotations

import re
from collections import defaultdict


def _keys(record: dict) -> list[tuple[str, str]]:
    keys = []
    email = str(record.get('email') or '').strip().casefold()
    if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        keys.append(('邮箱一致', email))
    phone = re.sub(r'\D', '', str(record.get('phone') or ''))
    if re.fullmatch(r'1[3-9]\d{9}', phone):
        keys.append(('手机号一致', phone))
    return keys


def annotate_possible_duplicates(records: list[dict]) -> list[dict]:
    """Annotate records in place; never automatically discard or combine them."""
    by_key = defaultdict(list)
    for item in records:
        for key in _keys(item):
            by_key[key].append(item['resume_id'])
    near = defaultdict(set)
    reasons = defaultdict(set)
    for (reason, _), ids in by_key.items():
        if len(ids) < 2:
            continue
        for resume_id in ids:
            near[resume_id].update(other for other in ids if other != resume_id)
            reasons[resume_id].add(reason)
    for item in records:
        resume_id = item['resume_id']
        item['possible_duplicate_with'] = sorted(near[resume_id])
        item['duplicate_reasons'] = sorted(reasons[resume_id])
    return records


def collect_duplicate_groups(records: list[dict]) -> list[dict]:
    """Return disjoint connected groups when email and phone chains overlap."""
    annotate_possible_duplicates(records)
    by_id = {r['resume_id']: r for r in records}
    visited: set[int] = set()
    groups = []
    for record in records:
        start = record['resume_id']
        if start in visited or not record['possible_duplicate_with']:
            continue
        pending = [start]
        members = set()
        reasons = set()
        while pending:
            ident = pending.pop()
            if ident in visited:
                continue
            visited.add(ident)
            members.add(ident)
            candidate = by_id[ident]
            reasons.update(candidate['duplicate_reasons'])
            pending.extend(candidate['possible_duplicate_with'])
        if len(members) > 1:
            groups.append({'resume_ids': sorted(members), 'reasons': sorted(reasons)})
    return sorted(groups, key=lambda g: g['resume_ids'][0])
