"""PDF nguồn trong data/raw_data phải khớp data/reference/source_pdfs.json (A29).

Thay hoặc thêm PDF mà không chạy lại scripts/source_pdf_manifest.py --write thì test đỏ,
để biết bản nào của văn bản đang được parse (như khi PDF bị thay ở A6, A26).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import source_pdf_manifest as manifest  # noqa: E402
REGISTRY = json.loads((ROOT / "data/reference/document_versions.json").read_text(encoding="utf-8"))
ENTRIES = manifest.load()


def test_pdfs_on_disk_match_manifest():
    assert manifest.check(ENTRIES) == []


def test_every_pdf_belongs_to_one_registry_document():
    ids = {r["document_id"] for r in REGISTRY}
    assert all(e["document_id"] in ids for e in ENTRIES)
    documents = [e["document_id"] for e in ENTRIES]
    assert len(documents) == len(set(documents)), "Hai PDF cho cùng một văn bản"


def test_parsed_documents_have_a_source_pdf():
    parsed = {p.stem for p in (ROOT / "parser/parsed_jsons").glob("*.json")}
    missing = parsed - {e["document_id"] for e in ENTRIES}
    assert not missing, f"parsed_jsons không có PDF nguồn trong manifest: {sorted(missing)}"


def test_sha256_written_in_registry_matches_pdf():
    by_document = {e["document_id"]: e["sha256"] for e in ENTRIES}
    for record in REGISTRY:
        for digest in re.findall(r"sha256\s*:?\s*([0-9a-f]{16,64})", record.get("download_status") or ""):
            assert by_document[record["document_id"]].startswith(digest), record["document_id"]


def test_check_reports_replaced_and_unlisted_pdfs(tmp_path, monkeypatch):
    raw = tmp_path / "data" / "raw_data"
    raw.mkdir(parents=True)
    (raw / "a.pdf").write_bytes(b"%PDF-1 a")
    (raw / "b.pdf").write_bytes(b"%PDF-1 b")
    monkeypatch.setattr(manifest, "ROOT", tmp_path)
    monkeypatch.setattr(manifest, "RAW_DIR", raw)
    monkeypatch.setattr(manifest, "MANIFEST", tmp_path / "source_pdfs.json")
    entries = [{"path": "data/raw_data/a.pdf", "sha256": "0" * 64}, {"path": "data/raw_data/c.pdf", "sha256": "1" * 64}]
    errors = manifest.check(entries)
    assert any("b.pdf: PDF chưa có" in e for e in errors)
    assert any("c.pdf: có trong manifest" in e for e in errors)
    assert any("a.pdf: sha256 khác" in e for e in errors)
