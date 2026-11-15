"""Small, deterministic Chinese/English BM25 for local résumé tie-breaking.

This is lexical retrieval, NOT embedding-based semantic understanding and NOT a
candidate suitability score. It does not remove, select, or qualify anyone.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r'[\u3400-\u9fff]+|[a-z][a-z0-9+#.]*', re.IGNORECASE)
_HAN = re.compile(r'^[\u3400-\u9fff]+$')


def tokens(text: str, limit: int = 3000) -> list[str]:
    """Chinese character 2-/3-grams + complete Latin technical words."""
    out: list[str] = []
    for match in _TOKEN.finditer((text or '').lower()):
        segment=match.group()
        if _HAN.fullmatch(segment):
            if len(segment) == 1:
                continue
            out.extend(segment[i:i+2] for i in range(len(segment)-1))
            if len(segment) >= 3:
                out.extend(segment[i:i+3] for i in range(len(segment)-2))
        else:
            out.append(segment)
        if len(out) >= limit:
            return out[:limit]
    return out


def bm25_relevance(query: str, documents: list[str]) -> list[float]:
    """Returns bounded [0, 1] relative lexical relevance for an existing batch.

    Scores are not comparable across different hiring tasks or screening rounds.
    """
    if not documents:
        return []
    query_tokens=set(tokens(query, limit=1024))
    if not query_tokens:
        return [0.0] * len(documents)
    lengths=[]
    frequencies=[]
    document_frequency=Counter()
    for doc in documents:
        doc_tokens=tokens(doc, limit=3000)
        lengths.append(len(doc_tokens))
        counter=Counter(tok for tok in doc_tokens if tok in query_tokens)
        frequencies.append(counter)
        document_frequency.update(counter.keys())
    avg_length=max(1.0, sum(lengths) / len(documents))
    n=len(documents)
    k1,b=1.2,0.75
    results=[]
    for length, frequency in zip(lengths, frequencies):
        denominator_base=k1 * (1-b+b*length/avg_length)
        score=0.0
        for term, tf in frequency.items():
            df=document_frequency[term]
            idf=math.log1p((n-df+0.5)/(df+0.5))
            score += idf*(tf*(k1+1))/(tf+denominator_base)
        results.append(score)
    maximum=max(results,default=0.0)
    return [round(value/maximum,4) if maximum else 0.0 for value in results]
