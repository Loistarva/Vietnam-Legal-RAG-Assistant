"""Prepare/verify a proposed Dev-only zero-shot input without running inference."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "evaluation/manifests/dev_gold_30_selection_policy_v1.json"
QUERY_PATH = "evaluation/datasets/dev_gold_30_queries_v1.json"
MANIFEST_PATH = "evaluation/manifests/dev_gold_30_manifest.json"
IDS_PATH = "evaluation/rubrics/dev_gold_30_ids_v1.txt"
REVIEW_PATH = "evaluation/review/dev_gold_30_selection_review_v1.md"
CONTENT_FIELDS = ("answer", "explanation", "citations", "gold_article_ids", "gold_clause_ids", "gold_context_ids", "outdated_context_ids", "outdated_document_ids")
ANSWER_FIELDS = {"answer", "explanation", "citations", "gold_context_ids", "gold_clause_ids", "gold_article_ids"}


def canonical_hash(obj):
    return hashlib.sha256((json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()


def normalized(text):
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return " ".join("".join(c if c.isalnum() else " " for c in text if not unicodedata.combining(c)).split())


def expand_ids(spec):
    result = set()
    for token in spec.split(","):
        match = re.fullmatch(r"\s*HN_([0-9]{3})(?:[–-]HN_([0-9]{3}))?\s*", token)
        if not match:
            raise ValueError(f"Invalid exclusion token: {token}")
        lo, hi = int(match[1]), int(match[2] or match[1])
        if not 1 <= lo <= hi <= 300:
            raise ValueError(f"Invalid exclusion range: {token}")
        for number in range(lo, hi + 1):
            qid = f"HN_{number:03d}"
            if qid in result:
                raise ValueError(f"Duplicate exclusion: {qid}")
            result.add(qid)
    return result


@lru_cache(maxsize=None)
def blob(sha, path):
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Pinned full Git SHA required")
    available = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=ROOT,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if available.returncode:
        raise ValueError(f"Missing pinned commit {sha}; run python scripts/fetch_dev30_sources.py before offline checks")
    return subprocess.check_output(["git", "show", f"{sha}:{path}"], cwd=ROOT)


def load(sha, path):
    raw = blob(sha, path).decode("utf-8-sig")
    return [json.loads(line) for line in raw.splitlines() if line.strip()] if path.endswith(".jsonl") else json.loads(raw)


def keyed(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {key} in pinned source")
    return result


def context(policy):
    base, peer, added = (policy[k] for k in ("baseline_git_sha", "gold_audit_git_sha", "excluded_added_data_git_sha"))
    dev = load(base, "data/benchmark/queries_dev.json")
    gold = keyed(load(base, "data/benchmark/ground_truth.json"), "id")
    peer_gold = keyed(load(peer, "data/benchmark/ground_truth.json"), "id")
    chunks = keyed(load(base, "data/chunking_output/chunks.jsonl"), "chunk_id")
    other_chunks = keyed(load(added, "data/chunking_output/chunks.jsonl"), "chunk_id")
    docs = keyed(load(base, "data/reference/document_versions.json"), "document_id")
    all_test_ids, all_test_clauses, all_test_questions = set(), set(), set()
    for sha, labels in [(base, gold), (peer, peer_gold)]:
        test = load(sha, "data/benchmark/queries_test.json")
        keyed(test, "id")
        for q in test:
            all_test_ids.add(q["id"])
            all_test_questions.add(normalized(q["question"]))
            all_test_clauses.update(labels[q["id"]]["gold_clause_ids"])
    return dict(dev=keyed(dev, "id"), peer_dev=keyed(load(peer, "data/benchmark/queries_dev.json"), "id"), gold=gold, peer_gold=peer_gold, chunks=chunks, docs=docs,
                articles=keyed(load(base, "data/reference/article_index.json"), "article_id"),
                test_ids=all_test_ids, test_clauses=all_test_clauses, test_questions=all_test_questions,
                added_chunks=set(other_chunks) - set(chunks),
                added_documents={c["document_id"] for c in other_chunks.values()} - set(docs))


def rejection_reasons(q, ctx, policy):
    reasons = []
    qid = q.get("id")
    if qid not in ctx["dev"] or q.get("split") != "dev" or qid in ctx["test_ids"]:
        reasons.append("not_dev_or_test_id")
    if qid in expand_ids(policy["user_excluded_id_spec"]):
        reasons.append("user_requested_exclusion")
    if qid in policy["explicit_known_issue_ids"]:
        reasons.append("known_query_issue")
    if q != ctx["dev"].get(qid):
        reasons.append("query_differs_from_source")
    if q != ctx["peer_dev"].get(qid):
        reasons.append("query_changed_in_pending_d1")
    if ANSWER_FIELDS & set(q):
        reasons.append("answer_or_gold_leaked_into_model_input")
    try:
        if not isinstance(q.get("as_of_date"), str) or date.fromisoformat(q["as_of_date"]).isoformat() != q["as_of_date"]:
            raise ValueError()
    except (KeyError, ValueError):
        reasons.append("invalid_or_missing_as_of_date")
    question = q.get("question")
    if not isinstance(question, str) or not normalized(question):
        reasons.append("empty_question")
    elif normalized(question) in ctx["test_questions"]:
        reasons.append("test_question_collision")
    g = ctx["gold"].get(qid)
    if not g:
        return reasons + ["missing_gold"]
    if g.get("split") != "dev":
        reasons.append("gold_split_is_not_dev")
    for key, expected in {"review_status":"source_checked", "evidence_level":"full_text_checked", "answer_kind":"reviewed_answer", "mapping_status":"production_verified", "context_id_provenance":"production_index"}.items():
        if g.get(key) != expected:
            reasons.append(f"unverified_{key}")
    if g.get("gold_context_ids_confirmed") is not True or not g.get("verified_by") or not g.get("verified_at") or not g.get("answer", "").strip():
        reasons.append("incomplete_review_provenance")
    if qid not in ctx["peer_gold"] or any(g.get(f) != ctx["peer_gold"][qid].get(f) for f in CONTENT_FIELDS):
        reasons.append("substantive_gold_changed_in_pending_d1")
    clauses, ids, articles = g.get("gold_clause_ids", []), g.get("gold_context_ids", []), g.get("gold_article_ids", [])
    if not clauses or not ids or not articles or any(len(x) != len(set(x)) for x in [clauses, ids, articles]):
        reasons.append("missing_or_duplicate_gold_ids")
    if set(clauses) & ctx["test_clauses"]:
        reasons.append("test_clause_leakage")
    actual_clauses, actual_articles = set(), set()
    for cid in ids:
        chunk = ctx["chunks"].get(cid)
        if cid in ctx["added_chunks"]:
            reasons.append("uses_added_chunk")
        if not chunk:
            reasons.append("missing_corpus_chunk")
            continue
        if chunk["document_id"] in ctx["added_documents"]:
            reasons.append("uses_added_document")
        doc = ctx["docs"].get(chunk["document_id"])
        if not doc:
            reasons.append("unknown_document")
            continue
        if chunk.get("clause_id") != chunk.get("parent_clause_id") or not chunk.get("chunk_text", "").strip():
            reasons.append("incomplete_chunk_metadata_or_text")
        actual_clauses.add(chunk["clause_id"])
        actual_articles.add(f"{doc['file_code']}_D{int(chunk['article_number']):02d}")
        if (chunk.get("article_id") != f"{chunk['document_id']}_art_{int(chunk['article_number'])}" or
                not chunk["clause_id"].startswith(chunk["article_id"] + "_clause_")):
            reasons.append("inconsistent_corpus_hierarchy")
        meta = chunk.get("metadata", {})
        start = chunk.get("effective_from") or meta.get("effective_from") or chunk.get("effective_date") or meta.get("effective_date")
        end = chunk.get("effective_to") or meta.get("effective_to") or chunk.get("expiry_date") or meta.get("expiry_date")
        try:
            as_of = date.fromisoformat(q["as_of_date"])
            if not start or date.fromisoformat(start) > as_of or (end and as_of >= date.fromisoformat(end)):
                reasons.append("gold_not_in_force_at_query_date_or_unknown_start")
        except (KeyError, TypeError, ValueError):
            reasons.append("invalid_effectivity_date")
    if set(clauses) != actual_clauses or set(articles) != actual_articles:
        reasons.append("gold_clause_or_article_mapping_mismatch")
    complete_ids = {cid for cid,c in ctx["chunks"].items() if c.get("clause_id") in clauses}
    if set(ids) != complete_ids:
        reasons.append("incomplete_clause_chunk_coverage")
    for aid in articles:
        if ctx["articles"].get(aid, {}).get("verification_status") != "source_checked":
            reasons.append("article_not_source_checked")
    cited_articles = set()
    for citation in g.get("citations", []):
        doc = next((d for d in ctx["docs"].values() if citation.get("document_id") in
                    (d["document_id"], d["document_number"], d["file_code"])), None)
        number = re.match(r"[0-9]+", str(citation.get("article", "")))
        if not doc or not number or not str(citation.get("source_url", "")).startswith("https://"):
            reasons.append("invalid_citation_identity_or_url_format")
        else:
            cited_articles.add(f"{doc['file_code']}_D{int(number[0]):02d}")
    if cited_articles != set(articles):
        reasons.append("citation_article_mapping_mismatch")
    return sorted(set(reasons))


def check_selection(rows, ctx, policy):
    errors = []
    if len(rows) != 30 or len({q["id"] for q in rows}) != 30:
        errors.append("Exactly 30 unique query IDs required")
    if [q["id"] for q in rows] != policy["selected_ids"]:
        errors.append("ID order differs from reviewed selection policy")
    questions = [normalized(q["question"]) for q in rows]
    if len(set(questions)) != len(questions):
        errors.append("Duplicate normalized questions")
    for q in rows:
        errors += [f"{q['id']}: {r}" for r in rejection_reasons(q, ctx, policy)]
    return errors


def build(policy):
    if policy["status"] != "proposed_pending_user_and_dev2_review":
        raise ValueError("Preparation must not claim official approval")
    ctx = context(policy)
    rows = [deepcopy(ctx["dev"][qid]) for qid in policy["selected_ids"]]
    errors = check_selection(rows, ctx, policy)
    if errors:
        raise ValueError("\n".join(errors))
    exclusions = {qid: rejection_reasons(q, ctx, policy) for qid, q in ctx["dev"].items()}
    source_paths = ["data/benchmark/queries_dev.json", "data/benchmark/queries_test.json", "data/benchmark/ground_truth.json", "data/chunking_output/chunks.jsonl", "data/reference/article_index.json", "data/reference/document_versions.json"]
    manifest = dict(version="dev_gold_30_v1", status=policy["status"], created_on=policy["created_on"],
                    query_file=QUERY_PATH, ids_file=IDS_PATH, question_count=30, question_ids=policy["selected_ids"],
                    query_canonical_sha256=canonical_hash(rows), policy_canonical_sha256=canonical_hash(policy),
                    dataset_ids_hash=canonical_hash(policy["selected_ids"]),
                    baseline_git_sha=policy["baseline_git_sha"], gold_audit_git_sha=policy["gold_audit_git_sha"],
                    excluded_added_data_git_sha=policy["excluded_added_data_git_sha"],
                    source_git_blob_sha256={f: hashlib.sha256(blob(policy["baseline_git_sha"], f)).hexdigest() for f in source_paths},
                    user_excluded_ids=sorted(expand_ids(policy["user_excluded_id_spec"])),
                    excluded_added_chunk_ids=sorted(ctx["added_chunks"]), excluded_added_document_ids=sorted(ctx["added_documents"]),
                    distribution={field:dict(Counter(q[field] for q in rows)) for field in ["category", "question_type", "difficulty", "test_type"]},
                    remaining_reviewed_dev_ids=[qid for qid,g in ctx["gold"].items() if qid in ctx["dev"] and g.get("review_status")=="source_checked" and qid not in policy["selected_ids"]],
                    selected_gold_content_hash=canonical_hash([{f:ctx["gold"][qid].get(f) for f in ("id", *CONTENT_FIELDS)} for qid in policy["selected_ids"]]),
                    selection_checks="source_checked, content stable against D1 head, no added corpus, no Test ID/question/clause overlap; no model runs",
                    consumer_note="Proposed input only; Dev 2 must review/lock IDs, rubric guide, prompt/date policy and Freeze before official A/B.")
    sections = ["# 30 câu Dev đề xuất — kiểm tra trước bàn giao", "", "Status: proposed_pending_user_and_dev2_review. Không phải bảng điểm hoặc xác nhận pháp lý mới.", "", "File gửi chạy zero-shot: `../datasets/dev_gold_30_queries_v1.json` (chỉ query; không có đáp án).", "", f"Đã loại đúng {len(manifest['user_excluded_ids'])} ID người dùng chỉ định; dùng corpus cũ, không dùng 9 chunk thêm của PR #25.", "", "Đã đọc đối chiếu câu hỏi/đáp án với chunk source cho các ID dưới đây. Đây là rà soát nội dung trong repo, không thay review pháp lý độc lập hoặc xác minh hiệu lực mới ngoài corpus.", "", "## Phân bố", "", "```json", json.dumps(manifest["distribution"],ensure_ascii=False,indent=2), "```", "", "Giới hạn: tất cả Gold được chọn lấy từ Luật 52/2014 trong corpus cũ; không đại diện đầy đủ 75 Dev Gold hoặc toàn bộ văn bản/test_type. Không dùng chỉ số trên mẫu này để tuyên bố chất lượng toàn benchmark. Một số câu dùng chung Khoản; không coi chúng là 30 đơn vị chứng cứ độc lập."]
    for i,q in enumerate(rows,1):
        g = ctx["gold"][q["id"]]
        sections += ["", f"## {i:02d}. {q['id']}", "", q["question"], "", f"- Ngày áp dụng: {q['as_of_date']}; {q['question_type']}; {q['difficulty']}.", "- Trạng thái repo: source_checked/full_text_checked; nội dung Gold không đổi giữa baseline và D1 head.", "", "Đáp án tham chiếu từ repo (không đưa vào file inference):", "", g["answer"], "", "Chứng cứ corpus:"]
        for cid in g["gold_context_ids"]:
            sections += ["", f"`{cid}`", "", ctx["chunks"][cid]["chunk_text"]]
    sections += ["", "## Loại và chưa chọn", "", "Không chọn không đồng nghĩa câu đó sai. Danh sách dưới chỉ nêu lý do loại kỹ thuật; các câu hợp lệ còn lại không được chọn nhằm giữ đúng 30 câu và ưu tiên phạm vi đơn giản, nguồn trực tiếp.", ""]
    for qid,reasons in exclusions.items():
        if reasons:
            sections.append(f"- {qid}: {', '.join(reasons)}")
    return rows, manifest, "\n".join(sections) + "\n"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true",help="Write proposal artifacts after all checks pass; no benchmark mutation")
    args=parser.parse_args()
    try:
        policy=json.loads(POLICY.read_text(encoding="utf-8"))
        rows,manifest,review=build(policy)
        if args.write:
            existing=ROOT/MANIFEST_PATH
            if existing.exists() and json.loads(existing.read_text(encoding="utf-8")) != manifest:
                raise ValueError("Existing version differs; review and create v2 instead of overwriting v1")
            outputs={QUERY_PATH:json.dumps(rows,ensure_ascii=False,indent=2)+"\n", MANIFEST_PATH:json.dumps(manifest,ensure_ascii=False,indent=2)+"\n", IDS_PATH:"\n".join(policy["selected_ids"])+"\n", REVIEW_PATH:review}
            for filename,body in outputs.items():
                target=ROOT/filename
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(body,encoding="utf-8")
        exported=json.loads((ROOT/QUERY_PATH).read_text(encoding="utf-8-sig"))
        if exported != rows or json.loads((ROOT/MANIFEST_PATH).read_text(encoding="utf-8")) != manifest or (ROOT/IDS_PATH).read_text(encoding="utf-8").splitlines() != policy["selected_ids"]:
            raise ValueError("Exported queries/manifest/ID list differ from validated sources")
        print(json.dumps(dict(status="PASS",count=len(rows),excluded_user_ids=len(manifest["user_excluded_ids"]),added_chunks_excluded=len(manifest["excluded_added_chunk_ids"]),query_hash=manifest["query_canonical_sha256"],distribution=manifest["distribution"],review_status=manifest["status"]),ensure_ascii=True,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError,subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
