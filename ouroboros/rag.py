"""Our own small RAG engine: chunking, hybrid BM25 + TF-IDF search, diversity.

Pipeline
    Document -> chunk() -> Passage objects -> EvidencePool.search()

Scoring is a hybrid: 0.5 * bm25_norm + 0.5 * tfidf_cosine, where bm25_norm is
the Okapi BM25 score divided by the best BM25 score for that query (so it
lies in [0, 1]) and tfidf_cosine comes from the Phase I TF-IDF Encoder.

A greedy MMR-style re-rank then penalises candidates that share a document or
a domain with passages already picked, so one website cannot fill the top k.

Everything here is deterministic: no randomness, ties broken on pid.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from .retrieval import Encoder

if TYPE_CHECKING:  # Document is duck-typed at runtime, so no hard import
    from .sources import Document  # noqa: F401

BM25_K1 = 1.5
BM25_B = 0.75

_TOKEN = re.compile(r"[a-z0-9]+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")

STOP_WORDS = frozenset(
    """a about above after again all also am an and any are as at be because been
    before being below between both but by can could did do does doing down during
    each few for from further had has have having he her here hers him his how i if
    in into is it its itself just me more most my no nor not of off on once only or
    other our out over own same she should so some such than that the their them
    then there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your""".split()
)


@dataclass
class Passage:
    pid: str  # f"{doc_id}#{i}"
    doc_id: str
    source: str
    title: str
    url: str
    domain: str
    year: int | None
    text: str  # 2 to 4 sentences, about 60 to 120 words
    score: float = 0.0


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens with stop words removed."""
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP_WORDS]


def _split_sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    return [s for s in _SENT_SPLIT.split(text) if s]


def chunk(doc, max_words: int = 110) -> list[Passage]:
    """Split a document into passages of whole sentences, up to max_words each.

    A single sentence longer than max_words is cut on word boundaries. A short
    tail (under a quarter of max_words) is merged into the previous passage
    when the merge stays within 1.25 * max_words, so we do not emit stubs.
    """
    if max_words < 1:
        raise ValueError("max_words must be at least 1")
    groups: list[list[str]] = []  # each group is a list of words
    cur: list[str] = []
    for sent in _split_sentences(getattr(doc, "text", "") or ""):
        words = sent.split()
        if len(words) > max_words:
            if cur:
                groups.append(cur)
                cur = []
            for i in range(0, len(words), max_words):
                groups.append(words[i : i + max_words])
            continue
        if cur and len(cur) + len(words) > max_words:
            groups.append(cur)
            cur = []
        cur = cur + words
    if cur:
        groups.append(cur)

    if len(groups) >= 2 and len(groups[-1]) < max_words / 4:
        if len(groups[-2]) + len(groups[-1]) <= int(max_words * 1.25):
            groups[-2] = groups[-2] + groups[-1]
            groups.pop()

    out = []
    for i, words in enumerate(groups):
        out.append(
            Passage(
                pid=f"{doc.doc_id}#{i}",
                doc_id=doc.doc_id,
                source=doc.source,
                title=doc.title,
                url=doc.url,
                domain=doc.domain,
                year=getattr(doc, "year", None),
                text=" ".join(words),
            )
        )
    return out


class EvidencePool:
    """All passages seen in a run. Grows as hops fetch more documents."""

    def __init__(self, max_words: int = 110):
        self.max_words = max_words
        self._passages: list[Passage] = []
        self._by_pid: dict[str, Passage] = {}
        self._doc_ids: set[str] = set()
        # BM25 index state, rebuilt lazily when the pool has grown.
        self._indexed = 0
        self._tf: list[Counter] = []
        self._dl: list[int] = []
        self._df: Counter = Counter()
        self._avgdl = 0.0
        # TF-IDF state
        self._encoder: Encoder | None = None
        self._matrix: np.ndarray | None = None
        self._norms: np.ndarray | None = None
        self._fitted = 0

    # pool management

    def add_documents(self, docs) -> int:
        """Chunk and add documents. Returns the number of new passages.

        A document whose doc_id is already in the pool is skipped.
        """
        added = 0
        for doc in docs:
            if doc.doc_id in self._doc_ids:
                continue
            self._doc_ids.add(doc.doc_id)
            for p in chunk(doc, self.max_words):
                if p.pid in self._by_pid:
                    continue
                self._passages.append(p)
                self._by_pid[p.pid] = p
                added += 1
        return added

    def add_passages(self, passages) -> int:
        """Add ready-made passages as they are (closed-corpus mode). Returns the count added."""
        added = 0
        for p in passages:
            if p.pid in self._by_pid:
                continue
            self._doc_ids.add(p.doc_id)
            self._passages.append(p)
            self._by_pid[p.pid] = p
            added += 1
        return added

    def get(self, pid: str) -> Passage:
        return self._by_pid[pid]

    def __len__(self) -> int:
        return len(self._passages)

    def __contains__(self, pid: str) -> bool:
        return pid in self._by_pid

    def passages(self) -> list[Passage]:
        return list(self._passages)

    # lazy indexes

    @staticmethod
    def _index_text(p: Passage) -> str:
        return f"{p.title} {p.text}"

    def _refresh(self) -> None:
        n = len(self._passages)
        if n == self._indexed and n == self._fitted:
            return
        texts = [self._index_text(p) for p in self._passages]
        # BM25
        self._tf, self._dl, self._df = [], [], Counter()
        for t in texts:
            toks = tokenize(t)
            c = Counter(toks)
            self._tf.append(c)
            self._dl.append(len(toks))
            self._df.update(c.keys())
        self._avgdl = (sum(self._dl) / n) if n else 0.0
        self._indexed = n
        # TF-IDF (Phase I encoder), refit on the whole pool
        try:
            self._encoder = Encoder(texts)
            self._matrix = self._encoder.encode_many(texts)
            self._norms = np.linalg.norm(self._matrix, axis=1)
        except ValueError:  # empty vocabulary, e.g. only stop words
            self._encoder, self._matrix, self._norms = None, None, None
        self._fitted = n

    def _bm25(self, query: str) -> np.ndarray:
        n = len(self._passages)
        scores = np.zeros(n)
        q_terms = set(tokenize(query))
        if not q_terms or n == 0 or self._avgdl == 0:
            return scores
        for term in sorted(q_terms):
            df = self._df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            for i in range(n):
                f = self._tf[i].get(term, 0)
                if f == 0:
                    continue
                denom = f + BM25_K1 * (1 - BM25_B + BM25_B * self._dl[i] / self._avgdl)
                scores[i] += idf * f * (BM25_K1 + 1) / denom
        return scores

    def _cosine(self, query: str) -> np.ndarray:
        n = len(self._passages)
        if self._encoder is None or self._matrix is None:
            return np.zeros(n)
        qv = self._encoder.encode(query)
        qn = float(np.linalg.norm(qv))
        if qn == 0.0:
            return np.zeros(n)
        denom = self._norms * qn
        out = np.zeros(n)
        ok = denom > 0
        out[ok] = (self._matrix @ qv)[ok] / denom[ok]
        return out

    def hybrid_scores(self, query: str) -> np.ndarray:
        """Hybrid score for every passage in pool order."""
        self._refresh()
        bm = self._bm25(query)
        top = float(bm.max()) if len(bm) else 0.0
        bm_norm = bm / top if top > 0 else bm
        return 0.5 * bm_norm + 0.5 * self._cosine(query)

    # search

    def search(
        self,
        query: str,
        k: int = 6,
        exclude: set[str] = frozenset(),
        diversity: float = 0.5,
    ) -> list[Passage]:
        """Top-k passages for the query, hybrid scored then diversity re-ranked.

        Passages with a hybrid score of zero (no lexical overlap at all) are
        not returned, so fewer than k passages may come back. Returned
        Passage objects are copies carrying the hybrid score in .score; the
        pool's own passages are never mutated.

        diversity in [0, 1]. Each pick multiplies a candidate's score by
        (1 - diversity * penalty), where penalty rises with how many already
        picked passages share its domain (0.75 each) or its doc_id (a further
        0.25 each), capped at 1. diversity = 0 disables the re-rank.
        """
        if k <= 0 or not self._passages:
            return []
        diversity = min(1.0, max(0.0, float(diversity)))
        scores = self.hybrid_scores(query)
        cand = [
            i
            for i, p in enumerate(self._passages)
            if p.pid not in exclude and scores[i] > 0.0
        ]
        # stable base order: score desc, pid asc
        cand.sort(key=lambda i: (-scores[i], self._passages[i].pid))

        picked: list[int] = []
        if diversity == 0.0:
            picked = cand[:k]
        else:
            doc_n: Counter = Counter()
            dom_n: Counter = Counter()
            remaining = list(cand)
            while remaining and len(picked) < k:
                best, best_key = None, None
                for i in remaining:
                    p = self._passages[i]
                    pen = 0.75 * dom_n[p.domain] if p.domain else 0.0
                    pen += 0.25 * doc_n[p.doc_id]
                    pen = min(1.0, pen)
                    adj = float(scores[i]) * (1.0 - diversity * pen)
                    key = (-adj, -float(scores[i]), p.pid)
                    if best_key is None or key < best_key:
                        best, best_key = i, key
                picked.append(best)
                remaining.remove(best)
                p = self._passages[best]
                doc_n[p.doc_id] += 1
                if p.domain:
                    dom_n[p.domain] += 1

        out = []
        for i in picked:
            p = self._passages[i]
            out.append(
                Passage(
                    pid=p.pid, doc_id=p.doc_id, source=p.source, title=p.title,
                    url=p.url, domain=p.domain, year=p.year, text=p.text,
                    score=round(float(scores[i]), 4),
                )
            )
        return out
