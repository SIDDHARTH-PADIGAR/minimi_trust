"""
Minimal, dependency-free TF-IDF + cosine similarity.

Replaces an earlier scikit-learn/scipy-based implementation. scipy's
compiled Windows extensions can fail to load entirely on systems with a
constrained paging file/virtual memory limit — an environment problem,
not a code bug, but one this project has no reason to expose users to:
TF-IDF over a handful of short fact/key strings does not need a heavy
numerical library. Pure Python, stdlib only.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _tf(tokens: list[str]) -> Counter:
    return Counter(tokens)


def _idf(documents_tokens: list[list[str]]) -> dict[str, float]:
    n_docs = len(documents_tokens)
    doc_freq: Counter = Counter()
    for tokens in documents_tokens:
        doc_freq.update(set(tokens))
    # Smoothed IDF (avoids divide-by-zero for terms present in every document).
    return {term: math.log((1 + n_docs) / (1 + df)) + 1.0 for term, df in doc_freq.items()}


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = _tf(tokens)
    return {term: count * idf.get(term, 0.0) for term, count in tf.items()}


def _cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    common = vec_a.keys() & vec_b.keys()
    numerator = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return numerator / (norm_a * norm_b)


def tfidf_cosine_similarities(query: str, documents: list[str]) -> list[float]:
    """Returns one cosine similarity score per document, in the same
    order as `documents`. IDF is computed over query + all documents
    together. Never raises — an empty query or empty documents simply
    yields zero similarity."""
    all_texts = [query] + documents
    all_tokens = [_tokenize(t) for t in all_texts]
    idf = _idf(all_tokens)

    query_vec = _tfidf_vector(all_tokens[0], idf)
    doc_vecs = [_tfidf_vector(tokens, idf) for tokens in all_tokens[1:]]

    return [_cosine(query_vec, doc_vec) for doc_vec in doc_vecs]