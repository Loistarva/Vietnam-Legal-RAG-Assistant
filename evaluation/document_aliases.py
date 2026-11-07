"""Exact-span document alias lookup for citation consumers; no legal inference."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
VERSION = "document_aliases_v1"
NORMALIZER = "nfkd_casefold_alnum_v1"
ALIAS_KINDS = {"canonical_id","file_code","document_number","title","year","title_without_year",
               "title_with_issue_year","number_variant","type_number","type_year","family_law_short_title"}
TYPE_FORMS = {
    "Luật": ("Luật", "L"),
    "Nghị định": ("Nghị định", "NĐ", "ND"),
    "Nghị quyết": ("Nghị quyết", "NQ"),
    "Thông tư": ("Thông tư", "TT"),
    "Thông tư liên tịch": ("Thông tư liên tịch", "TTLT"),
}


def normalize_alias(value):
    if not isinstance(value, str):
        raise ValueError("Alias must be a string")
    value = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in value).split())


def canonical_hash(value):
    return hashlib.sha256((json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()


def iso_date(value, label):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label}: ISO date string required")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label}: ISO YYYY-MM-DD required")
    return value


def document_period(document):
    values = []
    for canonical, legacy in [("effective_from", "effective_date"), ("effective_to", "expiry_date")]:
        new = iso_date(document.get(canonical), canonical)
        old = iso_date(document.get(legacy), legacy)
        if new and old and new != old:
            raise ValueError(f"Conflicting {canonical}/{legacy}")
        values.append(new or old)
    if values[0] and values[1] and values[0] >= values[1]:
        raise ValueError("Effective period must have start < end")
    return tuple(values)


def validate_registry(registry):
    if not isinstance(registry, list) or not registry:
        raise ValueError("Registry must be a nonempty document array")
    seen = {field:set() for field in ("document_id", "document_number", "file_code")}
    for document in registry:
        if not isinstance(document, dict):
            raise ValueError("Document must be an object")
        for field in ("document_id", "document_number", "file_code", "title", "document_type", "issue_date"):
            if not isinstance(document.get(field), str) or not document[field].strip():
                raise ValueError(f"Missing/non-string document {field}")
        if not re.fullmatch(r"[a-z0-9_]+", document["document_id"]):
            raise ValueError("Invalid canonical document_id")
        if document["document_type"] not in TYPE_FORMS:
            raise ValueError("Unsupported document_type; review alias generation rules")
        for field, values in seen.items():
            key = normalize_alias(document[field])
            if not key or key in values:
                raise ValueError(f"Duplicate/empty document {field}")
            values.add(key)
        issue = iso_date(document["issue_date"], "issue_date")
        year = re.search(r"/(19[0-9]{2}|20[0-9]{2})/", document["document_number"])
        if year and year[1] != issue[:4]:
            raise ValueError("Document number year differs from issue_date year")
        start, _ = document_period(document)
        if start and start < issue:
            raise ValueError("Effective start precedes issue date; requires explicit source review")


def build_alias_map(registry):
    validate_registry(registry)
    entries = defaultdict(lambda: {"document_ids":set(), "forms":set(), "kinds":set()})
    documents = {}
    def add(form, document_id, kind):
        key = normalize_alias(form)
        if key:
            entry = entries[key]
            entry["document_ids"].add(document_id)
            entry["forms"].add(form)
            entry["kinds"].add(kind)
    for doc in registry:
        did, title, number = doc["document_id"], doc["title"], doc["document_number"]
        year = doc["issue_date"][:4]
        start, end = document_period(doc)
        documents[did] = dict(document_number=number, title=title, document_type=doc["document_type"],
                              issue_year=year, effective_from=start, effective_to=end,
                              temporal_scope=doc.get("provision_status", "document_level_only"),
                              source_fields={"effective_from":"effective_from" if "effective_from" in doc else "effective_date",
                                             "effective_to":"effective_to" if "effective_to" in doc else "expiry_date"})
        for form, kind in [(did,"canonical_id"),(doc["file_code"],"file_code"),(number,"document_number"),
                           (title,"title"),(year,"year"),(f"năm {year}","year")]:
            add(form,did,kind)
        bare_title = re.sub(r"\s+(?:năm\s+)?(?:19|20)[0-9]{2}$", "", title, flags=re.IGNORECASE)
        add(bare_title,did,"title_without_year")
        add(f"{bare_title} năm {year}",did,"title_with_issue_year")
        # Shorten only a known number, retaining its year. Never drop authority
        # from an unknown full number during lookup.
        numbers = {number}
        match = re.match(r"([0-9]+)([a-zA-Z]?)/(19[0-9]{2}|20[0-9]{2})/", number)
        if match:
            unpadded = f"{int(match[1])}{match[2]}/{match[3]}"
            suffix = number[match.end():]
            numbers |= {number[:match.end()-1], unpadded, f"{unpadded}/{suffix}"}
        for form in numbers:
            add(form,did,"number_variant")
            for kind in TYPE_FORMS[doc["document_type"]]:
                for spelling in (f"{kind} {form}",f"{kind} số {form}",f"{kind}{form}"):
                    add(spelling,did,"type_number")
        for kind in TYPE_FORMS[doc["document_type"]]:
            add(f"{kind} {year}",did,"type_year")
        if bare_title == "Luật Hôn nhân và gia đình":
            for name in ("Luật HNGĐ", "Luật HNGD", "Luật HN&GĐ"):
                for spelling in (name, f"{name} {year}", f"{name} năm {year}"):
                    add(spelling,did,"family_law_short_title")
    aliases = {key:{"document_ids":sorted(value["document_ids"]), "forms":sorted(value["forms"]),
                    "kinds":sorted(value["kinds"]), "ambiguous":len(value["document_ids"])>1,
                    "requires_identity_context":value["kinds"] <= {"year","type_year"}}
               for key,value in sorted(entries.items())}
    return dict(version=VERSION,normalization=NORMALIZER,review_status="pending_peer_review",registry_canonical_sha256=canonical_hash(registry),
                temporal_policy="Identity only; no newest/effective-date auto-selection; blank end is not proof of provision validity",
                documents=dict(sorted(documents.items())),aliases=aliases)


def validate_alias_map(artifact):
    if not isinstance(artifact, dict) or artifact.get("version") != VERSION or artifact.get("normalization") != NORMALIZER:
        raise ValueError("Unsupported alias map/normalizer version")
    docs, entries = artifact.get("documents"), artifact.get("aliases")
    if not isinstance(docs,dict) or not docs or not isinstance(entries,dict) or not entries:
        raise ValueError("Alias map documents/aliases must be nonempty objects")
    fingerprint=artifact.get("registry_canonical_sha256")
    if not isinstance(fingerprint,str) or not re.fullmatch(r"[a-f0-9]{64}",fingerprint):
        raise ValueError("Missing registry fingerprint")
    for did,doc in docs.items():
        if (not isinstance(did,str) or not re.fullmatch(r"[a-z0-9_]+",did) or not isinstance(doc,dict)
                or not isinstance(doc.get("issue_year"),str) or not re.fullmatch(r"[0-9]{4}",doc["issue_year"])
                or not isinstance(doc.get("document_type"),str) or doc["document_type"] not in TYPE_FORMS):
            raise ValueError("Invalid alias document metadata")
        document_period(doc)
    for key,entry in entries.items():
        if not isinstance(key,str) or not key or key != normalize_alias(key) or not isinstance(entry,dict):
            raise ValueError("Invalid normalized alias key/entry")
        ids = entry.get("document_ids")
        if (not isinstance(ids,list) or not ids or any(not isinstance(did,str) or did not in docs for did in ids)
                or len(set(ids)) != len(ids) or entry.get("ambiguous") is not (len(ids)>1)):
            raise ValueError("Invalid alias candidates/ambiguity flag")
        kinds=entry.get("kinds")
        if (not isinstance(kinds,list) or not kinds or any(not isinstance(k,str) or k not in ALIAS_KINDS for k in kinds)
                or len(set(kinds))!=len(kinds)):
            raise ValueError("Invalid alias kinds")
        if entry.get("requires_identity_context") is not (set(kinds) <= {"year","type_year"}):
            raise ValueError("Invalid weak-alias context flag")
    return artifact


def load_alias_map(path=None, registry_path=None):
    path = Path(path) if path else ROOT/"data/reference/document_aliases.json"
    registry_path = Path(registry_path) if registry_path else ROOT/"data/reference/document_versions.json"
    artifact = validate_alias_map(json.loads(path.read_text(encoding="utf-8-sig")))
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    if artifact != build_alias_map(registry):
        raise ValueError("Alias map stale/tampered or registry changed; rebuild and review")
    return artifact


def resolve_document_alias(text, artifact, *, year=None, document_type=None):
    """Resolve an exact citation span. Ambiguity remains unless explicit hints resolve it."""
    validate_alias_map(artifact)
    key = normalize_alias(text)
    if not key:
        raise ValueError("Alias must not be empty")
    if year is not None:
        if isinstance(year,bool) or not isinstance(year,(str,int)) or not re.fullmatch(r"(?:19|20)[0-9]{2}",str(year)):
            raise ValueError("Year hint must have four digits")
        year = str(year)
    canonical_type = None
    if document_type is not None:
        canonical_type = next((name for name,forms in TYPE_FORMS.items() if normalize_alias(document_type) in {normalize_alias(f) for f in forms}),None)
        if canonical_type is None:
            raise ValueError("Unknown document type hint")
    entry = artifact["aliases"].get(key)
    ids = list(entry["document_ids"]) if entry else []
    if any(did not in artifact["documents"] for did in ids):
        raise ValueError("Alias references unknown canonical document")
    ids = [did for did in ids if (year is None or artifact["documents"][did]["issue_year"]==year)
           and (canonical_type is None or artifact["documents"][did]["document_type"]==canonical_type)]
    weak_identity = entry.get("requires_identity_context",False) if entry else False
    status = "not_found" if not ids else "ambiguous" if len(ids)>1 else "insufficient_context" if weak_identity else "resolved"
    return dict(status=status,normalized_alias=key,document_id=ids[0] if status=="resolved" else None,candidates=ids)
