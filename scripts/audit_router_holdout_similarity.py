"""Screen frozen Router holdout v6 for near duplicates without running the Router."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from difflib import SequenceMatcher

from validate_router_holdout import DEFAULT_COMPARISON_PATHS, ROOT, validate_holdout

from agent.router.rule_router import strip_vietnamese_diacritics

HOLDOUT = ROOT / "evaluation/router_holdout/router_holdout_week10_v6.jsonl"
RULES = ROOT / "agent/router/rule_router.py"
EDIT_THRESHOLD = 0.82
BIGRAM_THRESHOLD = 0.65


def normalize(text):
    return " ".join(re.findall(r"[^\W_]+", strip_vietnamese_diacritics(text.casefold())))


def references(path):
    content = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".py":
        for node in ast.walk(ast.parse(content)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield f"line {node.lineno}", node.value
        return
    rows = (json.loads(line) for line in content.splitlines() if line.strip()) if path.suffix == ".jsonl" else json.loads(content)
    for index, row in enumerate(rows, 1):
        query = row.get("query", row.get("question"))
        if isinstance(query, str):
            yield str(row.get("id") or row.get("query_id") or f"record {index}"), query


def bigrams(text):
    tokens = text.split()
    return set(zip(tokens, tokens[1:]))


def sha256_lf(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main():
    result = validate_holdout(HOLDOUT, (*DEFAULT_COMPARISON_PATHS, RULES))
    print(f"Holdout: {len(result['rows'])} cases, SHA-256 LF {sha256_lf(HOLDOUT)}")
    print(f"Router source SHA-256 LF: {sha256_lf(RULES)}")
    print(f"Exact matches: {len(result['comparison_matches'])}; validation errors: {len(result['errors'])}")
    print(f"Review thresholds: character similarity >= {EDIT_THRESHOLD} or token-bigram Jaccard >= {BIGRAM_THRESHOLD}")
    if result["errors"]:
        return 1
    for path in (*DEFAULT_COMPARISON_PATHS, RULES):
        entries = [(ref, normalize(text)) for ref, text in references(path)]
        entries = [(ref, text, bigrams(text)) for ref, text in entries if text]
        relative = path.relative_to(ROOT).as_posix()
        print(f"\n{relative}: {len(entries)} references, SHA-256 LF {sha256_lf(path)}")
        for row in result["rows"]:
            query = normalize(row["query"])
            query_bigrams = bigrams(query)
            for reference, text, text_bigrams in entries:
                union = query_bigrams | text_bigrams
                jaccard = len(query_bigrams & text_bigrams) / len(union) if union else 0
                matcher = SequenceMatcher(None, query, text, autojunk=False)
                if jaccard < BIGRAM_THRESHOLD and matcher.real_quick_ratio() < EDIT_THRESHOLD:
                    continue
                similarity = matcher.ratio()
                if similarity >= EDIT_THRESHOLD or jaccard >= BIGRAM_THRESHOLD:
                    print(f"  {row['id']} | {reference} | {similarity:.3f} | {jaccard:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
