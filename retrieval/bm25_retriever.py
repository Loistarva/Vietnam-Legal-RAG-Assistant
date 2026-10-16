"""BM25 lexical retrieval over the shared normalized legal chunk schema."""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from embedding.vector_store import load_chunks


def tokenize(text: str) -> list[str]:
    """Simple Vietnamese-friendly tokenizer: lowercase whitespace terms, strip punctuation.

    Keeping Vietnamese words as whitespace-delimited terms preserves useful legal
    numbers and identifiers (for example, "Điều 56" and "2020/QH14").
    """
    terms = []
    for term in text.casefold().split():
        term = term.strip("""\"'“”‘’.,;:!?()[]{}<>|/\\-–—""")
        if term:
            terms.append(term)
    return terms


class BM25Index:
    """In-memory Okapi BM25 index over normalized chunks from ``load_chunks``."""

    def __init__(self, chunks: Sequence[dict[str, Any]], *, k1: float = 1.5, b: float = 0.75):
        if not chunks:
            raise ValueError("Danh sách chunk không được rỗng")
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("k1 phải > 0 và b phải nằm trong [0, 1]")
        self.k1, self.b = float(k1), float(b)
        self.chunks = []
        self.term_frequencies: list[Counter[str]] = []
        self.document_frequencies: Counter[str] = Counter()
        seen: set[str] = set()
        for chunk in chunks:
            chunk_id, text, metadata = chunk.get("chunk_id"), chunk.get("text"), chunk.get("metadata")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise ValueError("Mỗi chunk phải có chunk_id hợp lệ")
            if chunk_id in seen:
                raise ValueError(f"chunk_id bị trùng: {chunk_id}")
            if not isinstance(text, str) or not text.strip() or not isinstance(metadata, dict):
                raise ValueError(f"Chunk {chunk_id!r} thiếu text hoặc metadata hợp lệ")
            seen.add(chunk_id)
            # Include legal location fields in the index so exact references such
            # as "Điều 56" can match even when the article number is absent from
            # the chunk body itself.
            searchable_text = " ".join(
                [text, str(metadata.get("article_ref", "")),
                 str(metadata.get("article_number", "")),
                 str(metadata.get("clause_ref", ""))]
            )
            terms = tokenize(searchable_text)
            self.chunks.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})
            frequencies = Counter(terms)
            self.term_frequencies.append(frequencies)
            self.document_frequencies.update(frequencies.keys())
        self.document_count = len(self.chunks)
        self.document_lengths = [sum(freq.values()) for freq in self.term_frequencies]
        self.average_document_length = sum(self.document_lengths) / self.document_count

    @classmethod
    def from_file(cls, path: str, **kwargs: Any) -> "BM25Index":
        """Load flat/hierarchical chunk JSON with the shared embedding loader."""
        return cls(load_chunks(path), **kwargs)

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")
        query_terms = tokenize(query)
        if not query_terms:
            return []
        scores = []
        for i, frequencies in enumerate(self.term_frequencies):
            length = self.document_lengths[i]
            score = 0.0
            for term in query_terms:
                tf = frequencies.get(term, 0)
                if not tf:
                    continue
                df = self.document_frequencies[term]
                idf = math.log(1 + (self.document_count - df + 0.5) / (df + 0.5))
                denominator = tf + self.k1 * (1 - self.b + self.b * length / self.average_document_length)
                score += idf * tf * (self.k1 + 1) / denominator
            scores.append(score)
        ranked = sorted(range(self.document_count), key=lambda i: (-scores[i], i))
        return [{**self.chunks[i], "score": scores[i], "rank": rank}
                for rank, i in enumerate(ranked[:top_k], 1) if scores[i] > 0]


def main() -> int:
    parser = argparse.ArgumentParser(description="BM25 retrieval cho chunk pháp luật")
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--chunks", type=Path,
                        default=root / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json",
                        help="JSON chunk theo schema chung (mặc định: fixture Hôn nhân gia đình)")
    parser.add_argument("--query", required=True, help="Câu hỏi cần truy vấn")
    parser.add_argument("--top-k", type=int, default=10, help="Số kết quả tối đa (mặc định: 10)")
    parser.add_argument("--backend", choices=["elasticsearch", "local"], default="elasticsearch",
                        help="BM25 chạy trong Elasticsearch (mặc định) hoặc baseline in-memory")
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL"),
                        help="URL Elasticsearch (hoặc đặt biến ELASTICSEARCH_URL)")
    parser.add_argument("--index", default=os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev"),
                        help="Elasticsearch index đã chứa child chunks")
    parser.add_argument("--output", type=Path, help="Tùy chọn: lưu kết quả ra JSON")
    args = parser.parse_args()
    try:
        if args.backend == "local":
            index = BM25Index.from_file(str(args.chunks))
            results = index.search(args.query, args.top_k)
        else:
            if not args.elasticsearch_url:
                raise ValueError("Cần --elasticsearch-url hoặc biến ELASTICSEARCH_URL")
            try:
                from elasticsearch import Elasticsearch
            except ImportError as exc:
                raise RuntimeError("Cần cài elasticsearch client: pip install elasticsearch") from exc
            from retrieval.hybrid_retriever import ElasticsearchBM25Retriever
            client = Elasticsearch(args.elasticsearch_url)
            if not client.ping():
                raise ConnectionError(f"Không kết nối được Elasticsearch tại {args.elasticsearch_url}")
            results = ElasticsearchBM25Retriever(client, args.index).search(args.query, args.top_k)
        rendered = json.dumps(results, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            print(f"Đã lưu {len(results)} kết quả vào {args.output}")
        else:
            print(rendered)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
