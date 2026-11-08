"""Văn bản trùng title trong registry không được cùng có hiệu lực (A16).

TT 04/2020/TT-BTP và TT 15/2015/TT-BTP có title chính thức giống hệt nên embed_text của hai
văn bản mở đầu giống nhau. Hai văn bản chỉ tách được nhờ lọc theo thời điểm (retrieval/temporal.py,
mặc định là ngày hiện tại), nên khoảng hiệu lực của chúng phải rời nhau.
"""
from __future__ import annotations

import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "data/reference/document_versions.json").read_text(encoding="utf-8"))


def _overlap(a: dict, b: dict) -> bool:
    a_to, b_to = a.get("expiry_date") or "9999-12-31", b.get("expiry_date") or "9999-12-31"
    return a["effective_date"] < b_to and b["effective_date"] < a_to


def test_documents_with_the_same_title_are_never_in_force_together():
    by_title = defaultdict(list)
    for record in REGISTRY:
        by_title[" ".join(record["title"].split()).lower()].append(record)
    same_title = [group for group in by_title.values() if len(group) > 1]
    assert same_title, "registry không còn cặp trùng title; xóa test này cùng A16"
    for group in same_title:
        for a, b in combinations(group, 2):
            assert not _overlap(a, b), f"{a['document_id']} và {b['document_id']} trùng title và cùng có hiệu lực"
