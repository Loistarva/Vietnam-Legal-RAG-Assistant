"""Closed-catalog clarification and configuration validation."""
import pytest

from orchestration.clarification import Clarification, ClarificationCatalog, build_clarification, load_clarification_catalog
from orchestration.rag_pipeline import CLARIFY_MESSAGE
from orchestration.wiring import ServiceSettings, build_ask_service

pytestmark = [pytest.mark.req("FR3.4"), pytest.mark.req("FR3.4-AC4")]


def test_keeps_model_order_without_repeating_questions_or_echoing_unknown_text():
    catalog = ClarificationCatalog("v1", {"a": "Khi nào?", "b": "Ở đâu?"})
    result = build_clarification(["b", "Free model text", "b", "a", "Free model text"], catalog)
    assert result == Clarification(
        "Để xác định quy định áp dụng, vui lòng cho biết thêm:\n- Ở đâu?\n- Khi nào?",
        ("b", "a"), 1, "v1", False,
    )


@pytest.mark.req("FR3.6-AC1")
def test_no_catalog_uses_policy_message():
    assert build_clarification(["a", "b", "a"], None) == Clarification(CLARIFY_MESSAGE, (), 2, None, True)


def test_all_unknown_uses_catalog_generic():
    catalog = ClarificationCatalog("v1", {"a": "Khi nào?"}, "Vui lòng bổ sung thông tin.")
    assert build_clarification(["Free model text"], catalog) == Clarification(catalog.generic_message, (), 1, "v1", True)


@pytest.mark.req("NFR5.1")
@pytest.mark.parametrize(("data", "key"), [
    ({"facts": {}}, "version"),
    ({"version": "v1"}, "facts"),
    ({"version": " ", "facts": {}}, "version"),
    ({"version": "v1", "facts": []}, "facts"),
    ({"version": "v1", "facts": {"a": {}}}, "question"),
    ({"version": "v1", "facts": {"a": None}}, "question"),
    ({"version": "v1", "facts": {" ": {"question": "Khi nào?"}}}, "facts"),
    ({"version": "v1", "facts": {1: {"question": "Khi nào?"}}}, "facts"),
    ({"version": "v1", "facts": {"a": {"question": ""}}}, "question"),
    ({"version": "v1", "facts": {"a": {"question": 1}}}, "question"),
    ({"version": "v1", "facts": {}, "generic_message": None}, "generic_message"),
])
def test_invalid_catalog_names_key(data, key):
    with pytest.raises(ValueError, match=key):
        ClarificationCatalog.from_mapping(data)


@pytest.mark.req("NFR5.1")
def test_load_utf8_yaml(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text("version: v1\nfacts:\n  a:\n    question: Khi nào?\n    description: ignored\n", encoding="utf-8")
    assert load_clarification_catalog(path) == ClarificationCatalog("v1", {"a": "Khi nào?"}, CLARIFY_MESSAGE)


@pytest.mark.req("NFR5.1")
def test_configured_missing_file_propagates():
    settings = ServiceSettings.from_env({"LEGAL_RAG_PIPELINE_MODE": "mock",
                                         "LEGAL_RAG_CLARIFICATION_CATALOG": "nonexistent-test-catalog.yaml"})
    with pytest.raises(FileNotFoundError):
        build_ask_service(settings)
