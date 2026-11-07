from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from evaluation.document_aliases import build_alias_map, document_period, load_alias_map, normalize_alias, resolve_document_alias, validate_alias_map
from scripts.audit_document_metadata import audit_metadata

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def inputs():
    registry=json.loads((ROOT/"data/reference/document_versions.json").read_text(encoding="utf-8-sig"))
    chunks=[json.loads(line) for line in (ROOT/"data/chunking_output/chunks.jsonl").read_text(encoding="utf-8-sig").splitlines()]
    articles=json.loads((ROOT/"data/reference/article_index.json").read_text(encoding="utf-8-sig"))
    return registry,chunks,articles


@pytest.fixture(scope="module")
def aliases(inputs):
    return build_alias_map(inputs[0])


@pytest.mark.parametrize("text,expected",[
    ("52/2014/QH13","l_52_2014_qh13"),
    ("Luật số 52/2014/QH13","l_52_2014_qh13"),
    ("LUẬT HNGĐ năm 2014","l_52_2014_qh13"),
    ("luat hngd nam 2000","l_22_2000_qh10"),
    ("Luật HN&GĐ năm 1986","l_21_lct_hdnn7"),
    ("NĐ126/2014","nd_126_2014_nd_cp"),
    ("Nghị định 126/2014/NĐ‑CP","nd_126_2014_nd_cp"),
    ("TT 2a/2015/TT-BTP","tt_02a_2015_tt_btp"),
    ("Thông tư liên tịch số 01/2016/TTLT-TANDTC-VKSNDTC-BTP","ttlt_01_2016_ttlt_tandtc"),
    ("L01","l_52_2014_qh13"),
    ("l_52_2014_qh13","l_52_2014_qh13"),
])
def test_identity_variants_resolve_to_existing_canonical_id(aliases,text,expected):
    result=resolve_document_alias(text,aliases)
    assert result["status"]=="resolved"
    assert result["document_id"]==expected


def test_ambiguous_title_keeps_all_versions(aliases):
    result=resolve_document_alias("Luật Hôn nhân và gia đình",aliases)
    assert result["status"]=="ambiguous" and result["document_id"] is None
    assert set(result["candidates"])=={"l_52_2014_qh13","l_22_2000_qh10","l_21_lct_hdnn7"}


def test_explicit_year_disambiguates_without_effectivity_filter(aliases):
    assert resolve_document_alias("Luật HNGĐ",aliases,year=2000)["document_id"]=="l_22_2000_qh10"
    assert resolve_document_alias("Luật HNGĐ",aliases,year=2014)["document_id"]=="l_52_2014_qh13"
    assert resolve_document_alias("52/2014/QH13",aliases,year=2000)["status"]=="not_found"


def test_year_alone_never_resolves_even_with_one_candidate(aliases):
    result=resolve_document_alias("2019",aliases)
    assert len(result["candidates"])==1
    assert result["status"]=="insufficient_context" and result["document_id"] is None
    assert aliases["aliases"]["2019"]["requires_identity_context"] is True
    result=resolve_document_alias("2015",aliases,document_type="NĐ")
    assert result["status"]=="ambiguous" and len(result["candidates"])==2


@pytest.mark.parametrize("text",["Luật 2014","NQ 2024"])
def test_type_and_year_without_name_or_number_still_need_context(aliases,text):
    result=resolve_document_alias(text,aliases)
    assert result["status"]=="insufficient_context" and result["document_id"] is None


@pytest.mark.parametrize("text",["52/2014/QH12","126/2015/NĐ-CP","Luật HNGĐ 2026","Theo Luật HNGĐ 2014 thì sao?"])
def test_unknown_or_prose_input_not_fuzzily_mapped(aliases,text):
    assert resolve_document_alias(text,aliases)["status"]=="not_found"


@pytest.mark.parametrize("kwargs",[{"year":True},{"year":20.14},{"year":"2014-01-01"},{"document_type":"Bộ luật"}])
def test_bad_hints_rejected(aliases,kwargs):
    with pytest.raises(ValueError):resolve_document_alias("Luật HNGĐ",aliases,**kwargs)


@pytest.mark.parametrize("text",[None,[],True,"","   "])
def test_invalid_alias_input_rejected(aliases,text):
    with pytest.raises(ValueError):resolve_document_alias(text,aliases)


def test_year_uses_issuance_not_effective_year(aliases):
    doc=aliases["documents"]["l_52_2014_qh13"]
    assert doc["issue_year"]=="2014" and doc["effective_from"]=="2015-01-01"
    assert resolve_document_alias("Luật 2015",aliases)["status"]=="not_found"


@pytest.mark.parametrize("mode",["duplicate_id","duplicate_number","bad_id","missing_title","bad_date","conflicting_dates","reverse_period","year_mismatch"])
def test_invalid_registry_fails_instead_of_overwriting_aliases(inputs,mode):
    registry=deepcopy(inputs[0]); doc=registry[0]
    if mode=="duplicate_id":registry.append(deepcopy(doc))
    elif mode=="duplicate_number":registry[1]["document_number"]=doc["document_number"]
    elif mode=="bad_id":doc["document_id"]="Not canonical"
    elif mode=="missing_title":doc["title"]=""
    elif mode=="bad_date":doc["effective_date"]="2015-02-30"
    elif mode=="conflicting_dates":doc["effective_from"]="2016-01-01"
    elif mode=="reverse_period":doc["expiry_date"]="2014-01-01"
    else:doc["issue_date"]="2013-06-19"
    with pytest.raises(ValueError):build_alias_map(registry)


def test_existing_period_fields_retained_and_unknown_end_not_inferred(aliases):
    doc=aliases["documents"]["nd_126_2014_nd_cp"]
    assert doc["effective_to"] is None and doc["temporal_scope"]=="requires_review"
    assert doc["source_fields"]=={"effective_from":"effective_date","effective_to":"expiry_date"}
    assert document_period({"effective_date":"2015-01-01","effective_from":"2015-01-01"})==("2015-01-01",None)


@pytest.mark.parametrize("mode",["unknown_id","duplicate_candidate","wrong_ambiguity","bad_version","invalid_doc_type"])
def test_corrupted_map_rejected(aliases,mode):
    artifact=deepcopy(aliases); entry=artifact["aliases"]["luat hngd"]
    if mode=="unknown_id":entry["document_ids"]=["nonexistent"]
    elif mode=="duplicate_candidate":entry["document_ids"].append(entry["document_ids"][0])
    elif mode=="wrong_ambiguity":entry["ambiguous"]=False
    elif mode=="bad_version":artifact["version"]="unsupported"
    else:artifact["documents"][entry["document_ids"][0]]["document_type"]=[]
    with pytest.raises(ValueError):validate_alias_map(artifact)


@pytest.mark.parametrize("tamper",["registry","map"])
def test_loader_refuses_stale_or_forged_mapping(inputs,aliases,tmp_path,tamper):
    registry=deepcopy(inputs[0]); artifact=deepcopy(aliases)
    if tamper=="registry":registry[0]["title"]+=" updated"
    else:artifact["aliases"]["luat hngd 2014"]["document_ids"]=["l_22_2000_qh10"]
    r,a=tmp_path/"registry.json",tmp_path/"aliases.json"
    r.write_text(json.dumps(registry),encoding="utf-8");a.write_text(json.dumps(artifact),encoding="utf-8")
    with pytest.raises(ValueError):load_alias_map(a,r)


def test_actual_audit_and_generated_file(inputs,aliases):
    report=audit_metadata(*inputs)
    assert report["errors"]==[]
    assert report["registry_document_count"]==24 and report["corpus_chunk_count"]==2164
    assert load_alias_map()==aliases


@pytest.mark.parametrize("mode,code",[("doc_id","unknown_chunk_document"),("number","registry_chunk_mismatch"),
    ("date","registry_chunk_mismatch"),("bad_date","invalid_chunk_date"),("article","unknown_article_document"),
    ("duplicate","missing_or_duplicate_chunk_id")])
def test_audit_catches_corrupt_metadata_without_fixing_source(inputs,mode,code):
    registry,chunks,articles=deepcopy(inputs)
    if mode=="doc_id":chunks[0]["document_id"]="missing_doc"
    elif mode=="number":chunks[0]["metadata"]["document_number"]="wrong"
    elif mode=="date":chunks[0]["metadata"]["effective_to"]="2099-01-01"
    elif mode=="bad_date":chunks[0]["metadata"]["effective_from"]="bad-date"
    elif mode=="article":articles[0]["document_id"]=[]
    else:chunks.append(deepcopy(chunks[0]))
    assert any(e["code"]==code for e in audit_metadata(registry,chunks,articles)["errors"])


def test_normalization_is_idempotent_and_preserves_numeric_identifiers():
    assert normalize_alias("  NGHỊ ĐỊNH 126/2014/NĐ‑CP ")=="nghi dinh 126 2014 nd cp"
    key=normalize_alias("Luật HNGĐ năm 2014")
    assert normalize_alias(key)==key
    assert normalize_alias("52/2014/QH13")!=normalize_alias("52/2014/QH12")


@pytest.mark.parametrize("empty",["chunks","articles"])
def test_empty_audit_inputs_do_not_report_success(inputs,empty):
    registry,chunks,articles=inputs
    assert audit_metadata(registry,[] if empty=="chunks" else chunks,[] if empty=="articles" else articles)["errors"]


def test_wrong_chunk_namespace_detected(inputs):
    registry,chunks,articles=deepcopy(inputs)
    chunks[0]["chunk_id"]="other_doc_art_1_clause_1_chunk_1"
    assert any(e["code"]=="chunk_document_namespace_mismatch" for e in audit_metadata(registry,chunks,articles)["errors"])


def test_offline_audit_without_origin_testing_ref(monkeypatch,capsys):
    from scripts import audit_document_metadata as audit
    actual_run=subprocess.run
    def run(args,*pos,**kwargs):
        if args==["git","rev-parse","--verify","origin/testing^{commit}"]:
            return subprocess.CompletedProcess(args,128,stdout="",stderr="not fetched")
        return actual_run(args,*pos,**kwargs)
    monkeypatch.setattr(subprocess,"run",run)
    monkeypatch.setattr(sys,"argv",["audit_document_metadata.py"])
    assert audit.main()==0
    assert "PASS" in capsys.readouterr().out
