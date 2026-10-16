"""Command-line entry point for Elasticsearch's built-in BM25 retrieval."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Truy xuất BM25 bằng Elasticsearch")
    parser.add_argument("--query", required=True, help="Câu hỏi cần truy vấn")
    parser.add_argument("--top-k", type=int, default=10, help="Số kết quả tối đa")
    parser.add_argument("--elasticsearch-url", default=os.getenv("ELASTICSEARCH_URL"),
                        help="URL Elasticsearch (hoặc đặt biến ELASTICSEARCH_URL)")
    parser.add_argument("--index", default=os.getenv("ELASTICSEARCH_INDEX", "legal-child-chunks-dev"),
                        help="Tên index đã được nạp chunk")
    parser.add_argument("--output", type=Path, help="Tùy chọn: lưu kết quả ra JSON")
    args = parser.parse_args(argv)

    if not args.elasticsearch_url:
        parser.error("Cần --elasticsearch-url hoặc biến môi trường ELASTICSEARCH_URL")
    if args.top_k < 1:
        parser.error("--top-k phải là số nguyên lớn hơn 0")

    try:
        from elasticsearch import Elasticsearch
    except ImportError as exc:
        parser.error("Cần cài Elasticsearch client: pip install elasticsearch")
        raise exc  # pragma: no cover

    from retrieval.hybrid_retriever import ElasticsearchBM25Retriever

    client = Elasticsearch(args.elasticsearch_url)
    if not client.ping():
        parser.error(f"Không kết nối được Elasticsearch tại {args.elasticsearch_url}")
    results = ElasticsearchBM25Retriever(client, args.index).search(args.query, args.top_k)
    rendered = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Đã lưu {len(results)} kết quả vào {args.output}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
