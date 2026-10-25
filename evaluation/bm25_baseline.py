"""BM25 retrieval backed by the Elasticsearch index built by build_bm25_index.py."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from elasticsearch import Elasticsearch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
DEFAULT_INDEX = os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev")

# These fields are defined by build_bm25_index.py.
# Boost body text more than title/breadcrumb when ranking.
DEFAULT_FIELDS = ["content^3", "content_segmented^2", "title^1.5", "breadcrumb"]


class BM25Retriever:
    """Query an existing Elasticsearch index; does not build or re-load the index."""

    def __init__(
        self,
        es_url: str = DEFAULT_ES_URL,
        index_name: str = DEFAULT_INDEX,
        fields: Sequence[str] = DEFAULT_FIELDS,
        request_timeout: int = 30,
    ) -> None:
        if not fields:
            raise ValueError("fields không được rỗng")
        self.index_name = index_name
        self.fields = list(fields)
        self.client = Elasticsearch(es_url, request_timeout=request_timeout)

        if not self.client.ping():
            self.client.close()
            raise ConnectionError(f"Không kết nối được Elasticsearch tại {es_url}")
        if not self.client.indices.exists(index=self.index_name):
            self.client.close()
            raise ValueError(
                f"Index '{self.index_name}' chưa tồn tại. "
                "Hãy chạy build_bm25_index.py trước."
            )

    # ------------------------------------------------------------------
    # Kịch bản 1: xử lý MỘT query
    # ------------------------------------------------------------------
    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return ranked chunks with chunk_id, text, metadata, score and rank."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k phải là số nguyên lớn hơn 0")

        response = self.client.search(
            index=self.index_name,
            size=top_k,
            query={
                "multi_match": {
                    "query": query,
                    "fields": self.fields,
                    "type": "best_fields",
                }
            },
        )

        hits = response.get("hits", {}).get("hits", [])
        results: list[dict[str, Any]] = []
        for rank, hit in enumerate(hits, start=1):
            source = hit.get("_source", {})
            chunk_id = source.get("chunk_id") or hit.get("_id")
            content = source.get("content") or source.get("content_segmented") or ""
            metadata = {
                key: source[key]
                for key in (
                    "parent_id", "doc_id", "title", "breadcrumb", "article_ref"
                )
                if key in source
            }
            results.append({
                "chunk_id": str(chunk_id),
                "text": content,
                "metadata": metadata,
                "score": hit.get("_score"),
                "rank": rank,
            })
        return results

    # ------------------------------------------------------------------
    # Kịch bản 2: xử lý NHIỀU query (gọi lại search) và lưu dữ liệu
    # ------------------------------------------------------------------
    def run_batch(
        self,
        questions: list[dict[str, Any]],
        output_path: str | Path,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Chạy search cho từng câu hỏi rồi lưu toàn bộ kết quả ra file JSON."""
        results: list[dict[str, Any]] = []

        for number, item in enumerate(questions, start=1):
            question_id = item["id"]
            question = item["question"]

            chunks = self.search(question, top_k=top_k)
            results.append({
                "query_id": question_id,
                "question": question,
                "retrieved_chunk_ids": [chunk["chunk_id"] for chunk in chunks],
                "retrieved_chunks": [
                    {
                        "chunk_id": chunk["chunk_id"],
                        "rank": chunk["rank"],
                        "score": chunk["score"],
                    }
                    for chunk in chunks
                ],
            })
            #  print(
            #     f"[{number}/{len(questions)}] {question_id}: "
            #     f"{len(chunks)} chunks retrieved"
            # )

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return results

    def close(self) -> None:
        self.client.close()


def load_questions(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSON array of question objects (the format of queries_dev.json)."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"{path} phải chứa một JSON array; nếu là JSONL, cần loader khác."
        )

    questions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Phần tử thứ {position} không phải JSON object.")

        question_id = item.get("id")
        question = item.get("question")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError(f"Phần tử thứ {position} thiếu trường id hợp lệ.")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(
                f"Câu hỏi {question_id!r} thiếu trường question hợp lệ."
            )
        if question_id in seen_ids:
            raise ValueError(f"ID câu hỏi bị trùng: {question_id}")
        seen_ids.add(question_id)
        questions.append(item)

    return questions


def run_bm25(
    questions_path: str | Path,
    output_path: str | Path,
    *,
    es_url: str = DEFAULT_ES_URL,
    index_name: str = DEFAULT_INDEX,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Đọc tập câu hỏi -> chạy BM25 trên index có sẵn -> lưu kết quả.

    Không dựng index ở đây: dựng một lần bằng
    ``python -m retrieval.build_bm25_index`` (recreate=True khi corpus đổi), để
    es_url/index_name truyền vào luôn trỏ đúng index đã dựng và chunk cũ không tích tụ.
    """
    questions = load_questions(questions_path)
    retriever = BM25Retriever(es_url=es_url, index_name=index_name)
    try:
        return retriever.run_batch(questions, output_path, top_k=top_k)
    finally:
        retriever.close()