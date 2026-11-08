"""D1.1 structural metadata audit and deterministic registry-derived aliases."""

from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from evaluation.document_aliases import (
    build_alias_map,
    document_period,
    validate_registry,
)
from chunking.provision_periods import load_overrides

REGISTRY = "data/reference/document_versions.json"
CORPUS = "data/chunking_output/chunks.jsonl"
ALIASES = "data/reference/document_aliases.json"
REPORT = "reports/data/metadata_audit_20261103.md"  # Canonical plan filename, actual audit date in body.
EVIDENCE = "reports/data/metadata_audit_20261108.json"


def audit_metadata(registry, chunks, articles, provision_overrides=None):
    overrides = load_overrides() if provision_overrides is None else provision_overrides

    def allowed_period(record, chunk, doc):
        start, end = document_period(record)
        doc_start, doc_end = document_period(doc)
        if (doc_start and (not start or start < doc_start)) or (
            doc_end and (not end or end > doc_end)
        ):
            return False
        if (start, end) == (doc_start, doc_end):
            return True
        meta = chunk.get("metadata") or {}
        for override in overrides:
            if override.scope_of(
                chunk.get("document_id"),
                meta.get("article_number"),
                meta.get("clause_number"),
                chunk.get("point_ref"),
                meta.get("quoted_clause_number"),
            ):
                expected_end = min(d for d in (doc_end, override.effective_to) if d)
                if (start, end) == (doc_start, expected_end):
                    return True
        return False

    errors, warnings = [], []
    try:
        validate_registry(registry)
    except ValueError as exc:
        return dict(
            errors=[dict(code="invalid_registry", detail=str(exc))], warnings=[]
        )
    docs = {doc["document_id"]: doc for doc in registry}
    file_codes = {doc["file_code"]: doc["document_id"] for doc in registry}
    counts = Counter()
    if (
        not isinstance(chunks, list)
        or not chunks
        or not isinstance(articles, list)
        or not articles
    ):
        return dict(errors=[dict(code="invalid_corpus_or_article_index")], warnings=[])
    chunk_ids = set()
    mismatches = defaultdict(list)
    for chunk in chunks:
        if not isinstance(chunk, dict):
            errors.append(dict(code="nonobject_chunk"))
            continue
        cid, did = chunk.get("chunk_id"), chunk.get("document_id")
        if not isinstance(cid, str) or not cid or cid in chunk_ids:
            errors.append(dict(code="missing_or_duplicate_chunk_id", chunk_id=cid))
            continue
        chunk_ids.add(cid)
        if not isinstance(did, str) or did not in docs:
            errors.append(
                dict(code="unknown_chunk_document", chunk_id=cid, document_id=did)
            )
            continue
        counts[did] += 1
        if not cid.startswith(did + "_art_"):
            errors.append(
                dict(
                    code="chunk_document_namespace_mismatch",
                    chunk_id=cid,
                    document_id=did,
                )
            )
        meta = chunk.get("metadata")
        if not isinstance(meta, dict):
            errors.append(dict(code="invalid_chunk_metadata", chunk_id=cid))
            continue
        doc = docs[did]
        for name, value in (
            ("root_doc_id", chunk.get("doc_id")),
            ("metadata_doc_id", meta.get("doc_id")),
        ):
            if value != did:
                mismatches[(did, name, str(value), did)].append(cid)
        for origin, record in (("root", chunk), ("metadata", meta)):
            for name in ("document_number", "document_type", "issue_date"):
                if record.get(name) != doc.get(name):
                    mismatches[
                        (
                            did,
                            f"{origin}.{name}",
                            str(record.get(name)),
                            str(doc.get(name)),
                        )
                    ].append(cid)
            try:
                start, end = document_period(record)
                expected_start, expected_end = document_period(doc)
                if not allowed_period(record, chunk, doc):
                    # Root commonly carries only legacy effective_date, while
                    # effective_to is in metadata. Compare the combined view below.
                    if origin == "metadata":
                        mismatches[
                            (
                                did,
                                "metadata.period",
                                str((start, end)),
                                str((expected_start, expected_end)),
                            )
                        ].append(cid)
            except ValueError as exc:
                errors.append(
                    dict(
                        code="invalid_chunk_date",
                        chunk_id=cid,
                        origin=origin,
                        detail=str(exc),
                    )
                )
        combined = {
            **meta,
            **{
                k: v
                for k, v in chunk.items()
                if k
                in ("effective_from", "effective_to", "effective_date", "expiry_date")
                and v not in (None, "")
            },
        }
        try:
            if not allowed_period(combined, chunk, doc):
                mismatches[
                    (
                        did,
                        "combined.period",
                        str(document_period(combined)),
                        str(document_period(doc)),
                    )
                ].append(cid)
        except ValueError as exc:
            errors.append(
                dict(code="conflicting_chunk_dates", chunk_id=cid, detail=str(exc))
            )
        if chunk.get("title") != doc["title"] or meta.get("title") != doc["title"]:
            warnings.append(dict(code="title_variant", document_id=did, chunk_id=cid))
    for (did, field, actual, expected), ids in sorted(mismatches.items()):
        errors.append(
            dict(
                code="registry_chunk_mismatch",
                document_id=did,
                field=field,
                actual=actual,
                expected=expected,
                chunk_count=len(ids),
                sample_chunk_ids=ids[:3],
            )
        )
    article_ids = set()
    for article in articles:
        if (
            not isinstance(article, dict)
            or not isinstance(article.get("article_id"), str)
            or not article["article_id"]
            or article["article_id"] in article_ids
        ):
            errors.append(dict(code="invalid_or_duplicate_article"))
            continue
        article_ids.add(article["article_id"])
        identity = article.get("document_id")
        did = (
            (file_codes.get(identity) or (identity if identity in docs else None))
            if isinstance(identity, str)
            else None
        )
        if not did:
            errors.append(
                dict(code="unknown_article_document", article_id=article["article_id"])
            )
            continue
        if article.get("document_number") != docs[did]["document_number"]:
            errors.append(
                dict(
                    code="article_document_number_mismatch",
                    article_id=article["article_id"],
                )
            )
    for did, doc in docs.items():
        if not counts[did]:
            warnings.append(
                dict(code="registry_document_without_chunks", document_id=did)
            )
        if doc.get("provision_status") in ("requires_review", "document_level_only"):
            warnings.append(
                dict(
                    code="provision_effectivity_not_independently_verified",
                    document_id=did,
                    source_status=doc.get("provision_status"),
                )
            )
        source_url = doc.get("source_url", "")
        url = urlsplit(source_url if isinstance(source_url, str) else "")
        if url.scheme not in ("http", "https") or not url.netloc:
            warnings.append(dict(code="invalid_source_url_format", document_id=did))
        if not document_period(doc)[0]:
            warnings.append(dict(code="missing_effective_start", document_id=did))
    return dict(
        errors=errors,
        warnings=warnings,
        registry_document_count=len(registry),
        corpus_chunk_count=len(chunks),
        corpus_document_count=len(counts),
        article_count=len(articles),
        chunks_by_document=dict(sorted(counts.items())),
        requires_provision_review_ids=[
            d["document_id"]
            for d in registry
            if d.get("provision_status") == "requires_review"
        ],
    )


def render_report(audit, aliases, source):
    ambiguous = {k: v for k, v in aliases["aliases"].items() if v["ambiguous"]}
    warning_counts = Counter(w["code"] for w in audit["warnings"])
    lines = [
        "# D1.1 — Metadata audit và document aliases",
        "",
        "Ngày thực hiện: **08/11/2026** (Asia/Saigon). Tên file 20261103 giữ theo đường dẫn bàn giao trong kế hoạch; không phải ngày đã thực hiện audit.",
        "",
        f"Git SHA lúc audit: `{source['git_sha']}`; registry/corpus đọc từ working tree, fingerprints ở JSON evidence. Không đổi registry, corpus, benchmark hoặc Test.",
        "",
        "## Kết quả cấu trúc",
        "",
        f"- Registry: {audit['registry_document_count']} văn bản; corpus: {audit['corpus_chunk_count']} chunks / {audit['corpus_document_count']} văn bản; article index: {audit['article_count']} dòng.",
        f"- Structural errors: **{len(audit['errors'])}**; warnings: {len(audit['warnings'])}. Đây không phải xác nhận hiệu lực pháp lý độc lập hoặc xác nhận HTTP của nguồn.",
        f"- Alias keys: {len(aliases['aliases'])}; ambiguous keys: {len(ambiguous)}. Mỗi key giữ toàn bộ candidate IDs, không overwrite ứng viên hoặc tự chọn năm mới nhất.",
        "",
        "## Kiểm tra đã làm",
        "",
        "ID canonical, file_code và số hiệu không trùng; số hiệu/năm khớp issue_date (khi số hiệu có năm); title bắt buộc; ISO date và thứ tự issue/effectivity; canonical/legacy date không xung đột. Đối chiếu document_id, document_number, document_type, issue_date và effective period của chunk với registry; article index nối đúng văn bản/số hiệu.",
        "",
        "## Hiệu lực và vấn đề nguồn",
        "",
        "Registry hiện dùng effective_date/expiry_date; alias artifact ánh xạ thành effective_from/effective_to sau kiểm tra, không đổi tên field trong registry/consumer cũ. Ngày kết thúc là cận loại trừ. Alias resolver không lọc hiệu lực hoặc kết luận luật áp dụng; năm là năm ban hành, không phải năm hiệu lực.",
        "",
        "Cờ requires_review trong nguồn:",
        "",
        *[f"- `{did}`" for did in audit["requires_provision_review_ids"]],
        "",
        "Các cờ này đã có trong registry; không trình bày thành lỗi mới và không tự điền ngày hết hiệu lực cho điều khoản chỉ dựa vào trạng thái cấp văn bản. End=null có thể chưa mô hình hóa đầy đủ sửa đổi/bãi bỏ; không phải chứng minh mọi điều còn hiệu lực.",
        "",
        "Warning counts:",
        "",
        *[f"- {k}: {v}" for k, v in sorted(warning_counts.items())],
        "",
        "## Alias mơ hồ tiêu biểu",
        "",
        "```json",
    ]
    samples = {
        k: v["document_ids"]
        for k, v in ambiguous.items()
        if k
        in ("luat hngd", "luat hon nhan va gia dinh", "nghi dinh 2015", "2014", "2025")
    }
    lines += [
        json.dumps(samples, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Nguồn và giới hạn",
        "",
        f"Registry canonical SHA-256: `{aliases['registry_canonical_sha256']}`.",
        *[f"- {k}: raw file SHA-256 `{v}`" for k, v in source["file_sha256"].items()],
        "",
        "Không kiểm HTTP/redirect hay tự sửa source_url. Không suy diễn thêm văn bản mới, điều khoản đang còn hiệu lực hoặc tình trạng pháp lý từ alias. Nếu metadata đổi phải rebuild/review artifact; load_alias_map từ chối bản stale/tampered. Reviewer: Dev 2 + Dev 3; tình trạng pending_peer_review.",
        "",
        "Remote context:",
        "",
        source["remote_note"],
        "",
        "## Cách tái lập và bàn giao",
        "",
        "```powershell",
        "python scripts/audit_document_metadata.py",
        "python -m pytest test/test_document_aliases.py -q",
        "```",
        "",
        "Dùng --write để sinh alias map/evidence/report sau audit. Citation consumer đọc data/reference/document_aliases.json qua evaluation.document_aliases.load_alias_map; resolver nhận exact span và optional year/document_type. Sample/API chi tiết ở docs/document_aliases.md. Chưa sửa citation parser hoặc schema canonical của Dev 3.",
    ]
    if audit["errors"]:
        lines += [
            "",
            "## Structural errors",
            "",
            "```json",
            json.dumps(audit["errors"], ensure_ascii=False, indent=2),
            "```",
        ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        registry = json.loads((ROOT / REGISTRY).read_text(encoding="utf-8-sig"))
        chunks = [
            json.loads(line)
            for line in (ROOT / CORPUS).read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        articles = json.loads(
            (ROOT / "data/reference/article_index.json").read_text(encoding="utf-8-sig")
        )
        audit = audit_metadata(registry, chunks, articles)
        if audit["errors"]:
            print(json.dumps(audit, ensure_ascii=True, indent=2))
            return 1
        aliases = build_alias_map(registry)
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        remote = subprocess.run(
            ["git", "rev-parse", "--verify", "origin/testing^{commit}"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        remote_sha = remote.stdout.strip() if remote.returncode == 0 else None
        changed = (
            subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--name-only",
                    "HEAD",
                    remote_sha,
                    "--",
                    REGISTRY,
                    CORPUS,
                    "data/reference/article_index.json",
                    "data/normalized_metadata.json",
                ],
                cwd=ROOT,
                text=True,
            ).splitlines()
            if remote_sha
            else None
        )
        source = dict(
            git_sha=git_sha,
            remote_testing_sha=remote_sha,
            file_sha256={
                f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
                for f in (
                    REGISTRY,
                    CORPUS,
                    "data/reference/article_index.json",
                    "data/reference/provision_periods.json",
                )
            },
            remote_note=(
                f"origin/testing snapshot {remote_sha}; differing tracked input paths vs HEAD: {changed}. No automatic merge. Registry/corpus unchanged relative to this snapshot when absent from the list; article/source URL changes need integration review."
                if remote_sha
                else "origin/testing ref unavailable (e.g. single-branch/shallow checkout); remote comparison not performed. This does not imply data is up to date. Local fingerprints and structural audit remain available; no fetch/merge performed."
            ),
        )
        audit.update(
            audit_date="2026-11-08",
            review_status="pending_peer_review",
            source=source,
            alias_count=len(aliases["aliases"]),
            ambiguous_aliases={
                k: v["document_ids"]
                for k, v in aliases["aliases"].items()
                if v["ambiguous"]
            },
            alias_registry_canonical_sha256=aliases["registry_canonical_sha256"],
        )
        if args.write:
            outputs = {
                ALIASES: json.dumps(aliases, ensure_ascii=False, indent=2) + "\n",
                EVIDENCE: json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
                REPORT: render_report(audit, aliases, source),
            }
            for filename, body in outputs.items():
                target = ROOT / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
        actual = json.loads((ROOT / ALIASES).read_text(encoding="utf-8-sig"))
        if actual != aliases:
            raise ValueError(
                "Generated alias map differs from registry; rebuild/review"
            )
        print(
            json.dumps(
                {
                    k: audit[k]
                    for k in (
                        "registry_document_count",
                        "corpus_chunk_count",
                        "article_count",
                        "alias_count",
                        "review_status",
                    )
                },
                ensure_ascii=True,
            )
        )
        print(
            f"PASS: errors=0; warnings={len(audit['warnings'])}; ambiguous_aliases={len(audit['ambiguous_aliases'])}"
        )
        return 0
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
