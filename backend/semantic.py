"""Optional OFFLINE dense retrieval + cross-encoder reranking.

Semantic hits are leads for a human reviewer, *never proof of a qualification*.
The engine loads only explicitly configured local model directories; no model
is fetched implicitly while processing resumes.
"""
from __future__ import annotations

import os
import re
from collections import OrderedDict
from threading import RLock
from pathlib import Path
from typing import Protocol


class Encoder(Protocol):
    def encode(self, sentences, **kwargs): ...


class Reranker(Protocol):
    def predict(self, pairs, **kwargs): ...


def passages(pages: list[dict], max_items: int = 64) -> list[dict]:
    """Bounded, readable passages with stable source page numbers."""
    out: list[dict] = []
    for page in pages[:120]:
        text = str(page.get('text') or '')
        # Preserve short résumé lines and split long sections into manageable pieces.
        segments = re.split(r'[。！？!?；;\n]+', text)
        for segment in segments:
            segment = re.sub(r'\s+', ' ', segment).strip()
            if len(segment) < 8:
                continue
            if len(segment) <= 360:
                out.append({'page': page.get('page', 1), 'excerpt': segment})
            else:
                for i in range(0, len(segment), 280):
                    part = segment[i:i + 360]
                    if len(part) >= 8:
                        out.append({'page': page.get('page', 1), 'excerpt': part})
            if len(out) >= max_items:
                return out
    return out


def _cosine(left, right) -> float:
    # Explicit normalisation supports lightweight fake encoders in tests.
    import math
    a = [float(x) for x in left]
    b = [float(x) for x in right]
    if len(a) != len(b):
        raise ValueError('Embedding dimensions differ')
    divisor = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / divisor if divisor else 0.0


class SemanticMatcher:
    def __init__(self, encoder: Encoder | None = None, reranker: Reranker | None = None,
                 minimum_similarity: float = 0.55):
        self.encoder = encoder
        self.reranker = reranker
        self.minimum_similarity = minimum_similarity
        # Bounded RAM-only cache reused by subsequent screening rounds. Stores
        # embeddings, never persists model vectors/candidate text outside the
        # existing local database. Serialises CPU model inference across users.
        self._cache_limit = 4096
        self._cache: OrderedDict[str, object] = OrderedDict()
        self._cache_lock = RLock()

    @property
    def enabled(self) -> bool:
        return self.encoder is not None

    def search_many(self, terms: list[str], pages: list[dict]) -> dict[str, dict]:
        if not self.enabled:
            return {}
        unique_terms = list(dict.fromkeys(term.strip() for term in terms if term.strip()))
        snippets = passages(pages)
        if not unique_terms or not snippets:
            return {}
        # Reuse embeddings across resumes and *multiple screening rounds*;
        # recompute only genuinely new text. Bound memory to avoid unbounded
        # growth on large recruiting batches. No disk/model cloud calls.
        phrases = [*unique_terms, *[s['excerpt'] for s in snippets]]
        with self._cache_lock:
            missing = [value for value in dict.fromkeys(phrases) if value not in self._cache]
            computed = {}
            if missing:
                generated = list(self.encoder.encode(missing, normalize_embeddings=True,
                                                     show_progress_bar=False))
                if len(generated) != len(missing):
                    raise ValueError('Embedding model returned incomplete batch')
                computed = dict(zip(missing, generated))
            vectors = [self._cache[value] if value in self._cache else computed[value]
                       for value in phrases]
            for value in dict.fromkeys(phrases):
                if value in self._cache:
                    self._cache.move_to_end(value)
                else:
                    self._cache[value] = computed[value]
            while len(self._cache) > self._cache_limit:
                self._cache.popitem(last=False)
        document_vectors = vectors[len(unique_terms):]
        selections = {}
        pairs = []
        pair_meta = []
        for index, term in enumerate(unique_terms):
            sims = [_cosine(vectors[index], v) for v in document_vectors]
            top = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:5]
            if not top or sims[top[0]] < self.minimum_similarity:
                continue
            selections[term] = top[0]
            if self.reranker is not None:
                for i in top:
                    pairs.append((term, snippets[i]['excerpt']))
                    pair_meta.append((term, i))
        if pairs:
            rerank_scores = self.reranker.predict(pairs, show_progress_bar=False)
            best = {}
            for (term, index), score in zip(pair_meta, rerank_scores):
                if term not in best or float(score) > best[term][0]:
                    best[term] = (float(score), index)
            selections.update({term: value[1] for term, value in best.items()})
        return {term: {'page': snippets[i]['page'], 'excerpt': snippets[i]['excerpt'],
                       'source': 'local_semantic', 'review_required': True}
                for term, i in selections.items()}

    def search(self, term: str, pages: list[dict]) -> dict | None:
        return self.search_many([term], pages).get(term)


class LocalSemanticService:
    """Lazy local-only model loading; absence or failure is visible via status()."""
    def __init__(self, model_dir: str | None = None, reranker_dir: str | None = None,
                 fastembed_cache_dir: str | None = None):
        self.model_dir = model_dir if model_dir is not None else os.environ.get('HUIYAN_EMBEDDING_MODEL', '')
        self.reranker_dir = reranker_dir if reranker_dir is not None else os.environ.get('HUIYAN_RERANKER_MODEL', '')
        self.fastembed_cache_dir = fastembed_cache_dir if fastembed_cache_dir is not None else os.environ.get('HUIYAN_FASTEMBED_CACHE_DIR', '')
        self.matcher: SemanticMatcher | None = None
        self.error: str | None = None

    def status(self) -> dict:
        if not self.model_dir and not self.fastembed_cache_dir:
            return {'state': 'not_configured', 'message': '未安装语义模型，目前使用文字证据检索'}
        if self.error:
            return {'state': 'error', 'message': self.error}
        if self.matcher is not None:
            return {'state': 'ready', 'message': '本地语义证据检索已启用'}
        return {'state': 'configured', 'message': '本地模型将在首次筛选时加载'}

    def get_matcher(self) -> SemanticMatcher | None:
        if (not self.model_dir and not self.fastembed_cache_dir) or self.error:
            return None
        if self.matcher is not None:
            return self.matcher
        if not self.model_dir and self.fastembed_cache_dir:
            try:
                from .fastembed_cpu import FastEmbedEncoder
                encoder = FastEmbedEncoder(self.fastembed_cache_dir)
                self.matcher = SemanticMatcher(encoder=encoder)
                return self.matcher
            except (ImportError, OSError, RuntimeError, ValueError, TypeError) as exc:
                self.error = '离线中文语义模型加载失败，请检查已安装的模型和 FastEmbed 依赖'
                return None
        model = Path(self.model_dir).expanduser()
        if not model.is_dir():
            self.error = '找不到本地语义模型目录，请检查配置'
            return None
        if self.reranker_dir and not Path(self.reranker_dir).expanduser().is_dir():
            self.error = '找不到本地精排模型目录，请检查配置'
            return None
        try:
            from sentence_transformers import SentenceTransformer, CrossEncoder
            encoder = SentenceTransformer(str(model), local_files_only=True, trust_remote_code=False)
            reranker = (CrossEncoder(str(Path(self.reranker_dir).expanduser()), local_files_only=True,
                                     trust_remote_code=False) if self.reranker_dir else None)
            self.matcher = SemanticMatcher(encoder=encoder, reranker=reranker)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            # Avoid paths and package tracebacks (and personal machine details) in the HR UI.
            self.error = '语义模型加载失败，请检查本地模型文件和可选依赖'
            return None
        return self.matcher
