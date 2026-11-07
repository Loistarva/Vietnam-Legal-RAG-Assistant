import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chunking"))

from export_legal_chunks import load_corpus_scope  # noqa: E402

SCOPE = load_corpus_scope()
CHUNKS = [
    json.loads(line)
    for line in (ROOT / "data/chunking_output/chunks.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]


@pytest.mark.parametrize("doc_id", sorted(SCOPE))
def test_scoped_document_has_exactly_the_listed_articles(doc_id):
    parsed = json.loads((ROOT / "parser/parsed_jsons" / f"{doc_id}.json").read_text(encoding="utf-8"))
    assert SCOPE[doc_id] <= {str(a["article_number"]) for a in parsed["articles"]}
    in_corpus = {str(c["metadata"]["article_number"]) for c in CHUNKS if c["document_id"] == doc_id}
    assert in_corpus == SCOPE[doc_id]


def test_provision_evidence_is_inside_the_scope():
    periods = json.loads((ROOT / "data/reference/provision_periods.json").read_text(encoding="utf-8"))
    by_id = {c["chunk_id"]: c for c in CHUNKS}
    for override in periods["overrides"]:
        evidence = by_id[override["evidence_chunk_id"]]
        scope = SCOPE.get(evidence["document_id"])
        if scope is not None:
            assert str(evidence["metadata"]["article_number"]) in scope, override["id"]


def test_scope_entry_needs_a_reason(tmp_path):
    path = tmp_path / "scope.json"
    path.write_text(json.dumps({"documents": {"d": {"articles": ["1"]}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="reason"):
        load_corpus_scope(path)
