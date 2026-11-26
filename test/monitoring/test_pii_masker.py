import json

import pytest

from monitoring.pii_masker import PIIMasker


@pytest.mark.parametrize("raw,marker", [
    ("s11.person@example.test", "[EMAIL]"), ("0900000000", "[PHONE]"),
    ("+84 900 000 000", "[PHONE]"), ("001000000000", "[ID]"),
    ("Bearer S11_FAKE_TOKEN", "[SECRET]"), ("api_key=S11_FAKE_KEY", "[SECRET]"),
    ("sk-S11_fake_value_123456", "[SECRET]"),
])
def test_known_patterns(raw, marker):
    result = PIIMasker().mask_text(raw)
    assert raw not in result and marker in result


def test_secrets_and_nested_data_never_use_object_repr():
    class SecretObject:
        def __repr__(self):
            raise AssertionError("must not call repr")
    masker = PIIMasker(secret_values=["S11_OPAQUE_TEST_KEY"])
    result = masker.sanitize({"reason": {"Authorization": "secret", "X-API-Key": "secret",
                                        "note": ["s11.person@example.test", "S11_OPAQUE_TEST_KEY"],
                                        "object": SecretObject()}, "prompt": "private", "token_input": 12})
    encoded = json.dumps(result)
    assert "S11_OPAQUE_TEST_KEY" not in encoded and "example.test" not in encoded
    assert "Authorization" not in encoded and "X-API-Key" not in encoded and "prompt" not in result
    assert result["token_input"] == 12
    assert result["reason"]["object"] == "[UNSUPPORTED_VALUE]"


def test_debug_opt_in_still_masks_and_drops_secrets():
    result = PIIMasker(debug=True).sanitize({"query": "Email s11.person@example.test", "api_key": "secret"})
    assert result == {"query": "Email [EMAIL]"}


@pytest.mark.parametrize("debug", [False, True])
def test_header_aliases_and_environment_are_always_removed(debug):
    result = PIIMasker(debug=debug).sanitize({"reason": {"Authorization_Header": "Basic fake-credential",
                                                       "request_headers": {"Other": "private"},
                                                       "environment_values": {"Other": "private"}}})
    assert result == {"reason": {}}


def test_dates_versions_hashes_and_numeric_metrics_are_not_corrupted():
    value = {"as_of_date": "2026-11-22", "corpus_hash": "a" * 64, "version": "week11_v1",
             "count": 1234, "latency": 12.75}
    assert PIIMasker().sanitize(value) == value


def test_cycles_and_nonfinite_floats_do_not_break_sanitization():
    value = {"reason": {}}
    value["reason"]["loop"] = value
    assert "DEPTH_LIMIT" in json.dumps(PIIMasker().sanitize(value))
    assert PIIMasker().sanitize(float("nan")) is None
