from __future__ import annotations

"""Module 2: Hybrid Search — BM25 (Vietnamese) + Dense + RRF."""

import math
import os, re, sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME, EMBEDDING_MODEL,
                    EMBEDDING_DIM, BM25_TOP_K, DENSE_TOP_K, HYBRID_TOP_K)


@dataclass
class SearchResult:
    text: str
    score: float
    metadata: dict
    method: str  # "bm25", "dense", "hybrid"


def segment_vietnamese(text: str) -> str:
    """Segment Vietnamese text into words."""
    try:
        from underthesea import word_tokenize
        return word_tokenize(text, format="text").replace("_", " ")
    except Exception:
        return " ".join(re.findall(r"\w+", text.lower()))


class BM25Search:
    def __init__(self):
        self.corpus_tokens = []
        self.documents = []
        self.bm25 = None

    def index(self, chunks: list[dict]) -> None:
        """Build BM25 index from chunks."""
        self.documents = chunks
        self.corpus_tokens = [segment_vietnamese(c["text"]).lower().split() for c in chunks]
        try:
            from rank_bm25 import BM25Okapi
            self.bm25 = BM25Okapi(self.corpus_tokens)
        except Exception:
            self.bm25 = None

    def search(self, query: str, top_k: int = BM25_TOP_K) -> list[SearchResult]:
        """Search using BM25."""
        if not self.documents:
            return []
        tokenized_query = segment_vietnamese(query).lower().split()
        if self.bm25 is not None:
            scores = list(self.bm25.get_scores(tokenized_query))
        else:
            doc_freq = {t: sum(t in doc for doc in self.corpus_tokens) for t in set(tokenized_query)}
            avg_len = sum(len(doc) for doc in self.corpus_tokens) / max(len(self.corpus_tokens), 1)
            scores = []
            for doc in self.corpus_tokens:
                score = 0.0
                for token in tokenized_query:
                    tf = doc.count(token)
                    if not tf:
                        continue
                    idf = math.log((len(self.corpus_tokens) - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5) + 1)
                    score += idf * (tf * 2.5) / (tf + 1.5 * (1 - 0.75 + 0.75 * len(doc) / max(avg_len, 1)))
                scores.append(score)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            SearchResult(self.documents[i]["text"], float(scores[i]), self.documents[i].get("metadata", {}), "bm25")
            for i in top_indices if scores[i] > 0
        ]


class DenseSearch:
    def __init__(self):
        self._available = True
        try:
            from qdrant_client import QdrantClient
            self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        except Exception as exc:
            print(f"  ⚠️  Qdrant client unavailable: {exc}")
            self.client = None
            self._available = False
        self._encoder = None

    def _get_encoder(self):
        if self._encoder is None:
            if os.getenv("USE_LOCAL_MODELS") != "1" and os.getenv("ALLOW_MODEL_DOWNLOAD") != "1":
                raise RuntimeError("Dense encoder disabled; set USE_LOCAL_MODELS=1 or ALLOW_MODEL_DOWNLOAD=1 to enable")
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(EMBEDDING_MODEL)
        return self._encoder

    def index(self, chunks: list[dict], collection: str = COLLECTION_NAME) -> None:
        """Index chunks into Qdrant."""
        if not self._available or self.client is None or not chunks:
            return
        try:
            from qdrant_client.models import Distance, PointStruct, VectorParams

            self.client.recreate_collection(
                collection,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            texts = [c["text"] for c in chunks]
            vectors = self._get_encoder().encode(texts, show_progress_bar=True)
            points = [
                PointStruct(id=i, vector=v.tolist(), payload={**chunks[i].get("metadata", {}), "text": chunks[i]["text"]})
                for i, v in enumerate(vectors)
            ]
            self.client.upsert(collection_name=collection, points=points)
        except Exception as exc:
            print(f"  ⚠️  Dense indexing skipped: {exc}")
            self._available = False

    def search(self, query: str, top_k: int = DENSE_TOP_K, collection: str = COLLECTION_NAME) -> list[SearchResult]:
        """Search using dense vectors."""
        if not self._available or self.client is None:
            return []
        try:
            query_vector = self._get_encoder().encode(query).tolist()
            response = self.client.query_points(collection_name=collection, query=query_vector, limit=top_k)
            points = getattr(response, "points", response)
            return [
                SearchResult(
                    pt.payload.get("text", ""),
                    float(pt.score),
                    {k: v for k, v in pt.payload.items() if k != "text"},
                    "dense",
                )
                for pt in points if getattr(pt, "payload", None)
            ]
        except Exception as exc:
            print(f"  ⚠️  Dense search skipped: {exc}")
            self._available = False
            return []


def reciprocal_rank_fusion(results_list: list[list[SearchResult]], k: int = 60,
                           top_k: int = HYBRID_TOP_K) -> list[SearchResult]:
    """Merge ranked lists using RRF: score(d) = Σ 1/(k + rank)."""
    rrf_scores: dict[str, dict] = {}
    for results in results_list:
        for rank, result in enumerate(results):
            if result.text not in rrf_scores:
                rrf_scores[result.text] = {"score": 0.0, "result": result}
            rrf_scores[result.text]["score"] += 1.0 / (k + rank + 1)
    ranked = sorted(rrf_scores.values(), key=lambda item: item["score"], reverse=True)[:top_k]
    return [
        SearchResult(item["result"].text, float(item["score"]), item["result"].metadata, "hybrid")
        for item in ranked
    ]


class HybridSearch:
    """Combines BM25 + Dense + RRF. (Đã implement sẵn — dùng classes ở trên)"""
    def __init__(self):
        self.bm25 = BM25Search()
        self.dense = DenseSearch()

    def index(self, chunks: list[dict]) -> None:
        self.bm25.index(chunks)
        self.dense.index(chunks)

    def search(self, query: str, top_k: int = HYBRID_TOP_K) -> list[SearchResult]:
        bm25_results = self.bm25.search(query, top_k=BM25_TOP_K)
        dense_results = self.dense.search(query, top_k=DENSE_TOP_K)
        return reciprocal_rank_fusion([bm25_results, dense_results], top_k=top_k)


if __name__ == "__main__":
    print(f"Original:  Nhân viên được nghỉ phép năm")
    print(f"Segmented: {segment_vietnamese('Nhân viên được nghỉ phép năm')}")
