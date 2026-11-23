"""Unit tests for runtime config and model-run manifest validator (D3.4)."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, QwenGatewayConfig
from model_gateway.run_metadata import (
    ManifestValidationError,
    assert_valid_run_manifest,
    build_model_run_manifest,
    collect_hardware_profile,
    validate_run_manifest,
    validate_runtime_config,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
SHA_F = "f" * 64
SHA_1 = "1" * 64


def _valid_manifest() -> dict:
    return {
        "manifest_version": "d3.4.run_manifest.v1",
        "git_branch": "feature/week11-dev3-contracts-gateway",
        "git_sha": "03a498924d0d134d2abc861599db94920f7291db",
        "working_tree_clean": True,
        "benchmark_sha256": SHA_A,
        "dataset_ids_hash": SHA_B,
        "corpus_hash": SHA_C,
        "config_hashes": {
            "retrieval": SHA_D,
            "rerank": SHA_E,
            "model": SHA_F,
            "threshold": SHA_1,
        },
        "precomputed_retrieval": False,
        "precomputed_artifact": None,
        "runtime": {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "model_config_version": "local_qwen_v1.1",
            "model_digest": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
            "ollama_version": "0.40.16",
            "prompt_version": "v1.2_controlled_rag",
            "num_ctx": 8192,
            "num_predict": 1024,
            "temperature": 0.0,
            "repeat_penalty": 1.0,
            "cache": "OFF",
            "cache_enabled": False,
            "fallback": "LOCKED",
            "fallback_locked": True,
        },
        "hardware": {
            "os": "Windows-11-10.0.26100-SP0",
            "cpu": "AMD64 Family 25 Model 80",
            "gpu": "NVIDIA GeForce RTX 3060",
            "vram": "12288 MiB",
        },
        "started_at": "2026-11-23T10:00:00+00:00",
        "finished_at": "2026-11-23T10:05:00Z",
    }


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
@pytest.mark.req("NFR4.3")
@pytest.mark.req("NFR2.3")
def test_valid_manifest_and_runtime_config_pass_official_check(tmp_path: Path):
    assert validate_runtime_config(DEFAULT_CONFIG_PATH, official=True) == []
    manifest = _valid_manifest()
    assert validate_run_manifest(manifest, official=True) == []

    manifest_file = tmp_path / "run_manifest.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = assert_valid_run_manifest(manifest_file, official=True)
    assert loaded["git_sha"] == manifest["git_sha"]


@pytest.mark.req("NFR4.1")
def test_official_mode_rejects_dirty_tree_nonzero_temp_cache_on_and_unlocked_fallback():
    base = _valid_manifest()

    dirty = deepcopy(base)
    dirty["working_tree_clean"] = False
    assert any("working_tree_clean" in err for err in validate_run_manifest(dirty, official=True))
    assert validate_run_manifest(dirty, official=False) == []

    warm_temp = deepcopy(base)
    warm_temp["runtime"]["temperature"] = 0.2
    assert any("temperature" in err for err in validate_run_manifest(warm_temp, official=True))
    assert validate_run_manifest(warm_temp, official=False) == []

    cached = deepcopy(base)
    cached["runtime"]["cache_enabled"] = True
    cached["runtime"]["cache"] = "ON"
    assert any("cache" in err for err in validate_run_manifest(cached, official=True))

    unlocked = deepcopy(base)
    unlocked["runtime"]["fallback_locked"] = False
    unlocked["runtime"]["fallback"] = "UNLOCKED"
    assert any("fallback" in err for err in validate_run_manifest(unlocked, official=True))

    cfg_errors = validate_runtime_config(QwenGatewayConfig(temperature=0.3), official=True)
    assert any("temperature" in err for err in cfg_errors)


@pytest.mark.req("NFR4.2")
@pytest.mark.req("NFR4.3")
@pytest.mark.parametrize(
    "mutator,expected_field",
    [
        (lambda m: m.pop("git_branch"), "git_branch"),
        (lambda m: m.__setitem__("git_sha", "unknown"), "git_sha"),
        (lambda m: m.__setitem__("working_tree_clean", "true"), "working_tree_clean"),
        (lambda m: m.__setitem__("benchmark_sha256", "not-sha"), "benchmark_sha256"),
        (lambda m: m.pop("dataset_ids_hash"), "dataset_ids_hash"),
        (lambda m: m.pop("corpus_hash"), "corpus_hash"),
        (lambda m: m["config_hashes"].pop("retrieval"), "config_hashes.retrieval"),
        (lambda m: m["config_hashes"].pop("rerank"), "config_hashes.rerank"),
        (lambda m: m["config_hashes"].pop("model"), "config_hashes.model"),
        (lambda m: m["config_hashes"].pop("threshold"), "config_hashes.threshold"),
        (lambda m: m["runtime"].pop("model_digest"), "runtime.model_digest"),
        (lambda m: m["runtime"].pop("ollama_version"), "runtime.ollama_version"),
        (lambda m: m["runtime"].pop("prompt_version"), "runtime.prompt_version"),
        (lambda m: m["runtime"].__setitem__("num_ctx", True), "runtime.num_ctx"),
        (lambda m: m.pop("started_at"), "started_at"),
        (lambda m: m.__setitem__("finished_at", "2026-11-23T09:59:00Z"), "finished_at"),
    ],
)
def test_manifest_validator_reports_exact_missing_or_invalid_fields(mutator, expected_field: str):
    manifest = _valid_manifest()
    mutator(manifest)
    errors = validate_run_manifest(manifest, official=False)
    assert any(expected_field in err for err in errors), errors
    with pytest.raises(ManifestValidationError, match=expected_field):
        assert_valid_run_manifest(manifest, official=False)


@pytest.mark.req("NFR2.3")
def test_manifest_requires_hardware_os_cpu_gpu_vram():
    for hw_field in ("os", "cpu", "gpu", "vram"):
        manifest = _valid_manifest()
        manifest["hardware"].pop(hw_field)
        errors = validate_run_manifest(manifest)
        assert any(f"hardware.{hw_field}" in err for err in errors)

    hw = collect_hardware_profile()
    assert set(hw.keys()) == {"os", "cpu", "gpu", "vram"}
    assert all(isinstance(v, str) and v.strip() for v in hw.values())


@pytest.mark.req("NFR4.2")
def test_precomputed_retrieval_requires_artifact_hash_and_builder_roundtrips(tmp_path: Path):
    manifest = _valid_manifest()
    manifest["precomputed_retrieval"] = True
    manifest["precomputed_artifact"] = {"path": "retrieval/results/dev.json"}
    errors = validate_run_manifest(manifest)
    assert any("precomputed_artifact" in err and "sha256" in err for err in errors)

    bench = tmp_path / "bench.json"
    corpus = tmp_path / "chunks.jsonl"
    ret_cfg = tmp_path / "ret.yaml"
    rerank_cfg = tmp_path / "rerank.yaml"
    thresh_cfg = tmp_path / "thresh.yaml"
    precomp = tmp_path / "precomputed.jsonl"
    for p, content in [
        (bench, "[]\n"),
        (corpus, '{"chunk_id":"c1"}\n'),
        (ret_cfg, "top_k: 50\n"),
        (rerank_cfg, "top_k: 10\n"),
        (thresh_cfg, "min_top1: 0.5\n"),
        (precomp, '{"query_id":"HN_001"}\n'),
    ]:
        p.write_text(content, encoding="utf-8")

    built = build_model_run_manifest(
        benchmark_path=bench,
        dataset_ids=["HN_001"],
        corpus_path=corpus,
        retrieval_config_path=ret_cfg,
        rerank_config_path=rerank_cfg,
        model_config_path=DEFAULT_CONFIG_PATH,
        threshold_config_path=thresh_cfg,
        prompt_version="v1.2_controlled_rag",
        model_digest="sha256:digest",
        ollama_version="0.40.16",
        precomputed_artifact_path=precomp,
        hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
    )
    assert validate_run_manifest(built, official=False) == []


@pytest.mark.req("NFR4.1")
@pytest.mark.parametrize("field", ["temperature", "repeat_penalty", "timeout_seconds"])
@pytest.mark.parametrize("bad_num", [float("nan"), float("inf"), float("-inf")])
def test_runtime_config_and_manifest_reject_non_finite_numbers(field: str, bad_num: float):
    base_cfg = QwenGatewayConfig().model_dump()
    base_cfg[field] = bad_num
    for is_official in (True, False):
        cfg_errors = validate_runtime_config(base_cfg, official=is_official)
        assert cfg_errors, f"Expected error for runtime config {field}={bad_num}"

        manifest = _valid_manifest()
        manifest["runtime"][field] = bad_num
        mf_errors = validate_run_manifest(manifest, official=is_official)
        assert any(field in err for err in mf_errors), mf_errors


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
@pytest.mark.req("NFR4.3")
def test_manifest_detects_model_config_override_hash_mismatch(tmp_path: Path):
    bench = tmp_path / "bench.json"
    corpus = tmp_path / "chunks.jsonl"
    ret_cfg = tmp_path / "ret.yaml"
    rerank_cfg = tmp_path / "rerank.yaml"
    thresh_cfg = tmp_path / "thresh.yaml"
    model_cfg = tmp_path / "model_8192.yaml"
    for p, content in [
        (bench, "[]\n"),
        (corpus, '{"chunk_id":"c1"}\n'),
        (ret_cfg, "top_k: 50\n"),
        (rerank_cfg, "top_k: 10\n"),
        (thresh_cfg, "min_top1: 0.5\n"),
        (model_cfg, DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")),
    ]:
        p.write_text(content, encoding="utf-8")

    # gateway_config ghi đè num_ctx=4096 trong khi file config băm có num_ctx=8192
    override_cfg = QwenGatewayConfig(num_ctx=4096)
    built = build_model_run_manifest(
        benchmark_path=bench,
        dataset_ids=["HN_001"],
        corpus_path=corpus,
        retrieval_config_path=ret_cfg,
        rerank_config_path=rerank_cfg,
        model_config_path=model_cfg,
        threshold_config_path=thresh_cfg,
        prompt_version="v1.2_controlled_rag",
        model_digest="sha256:digest",
        ollama_version="0.40.16",
        gateway_config=override_cfg,
        hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
    )
    built["working_tree_clean"] = True

    # Official run phải từ chối và chỉ rõ model_config_hash_mismatch + num_ctx
    official_errors = validate_run_manifest(built, official=True)
    assert any("model_config_hash_mismatch" in err and "num_ctx" in err for err in official_errors), official_errors

    with pytest.raises(ManifestValidationError, match="model_config_hash_mismatch"):
        build_model_run_manifest(
            benchmark_path=bench,
            dataset_ids=["HN_001"],
            corpus_path=corpus,
            retrieval_config_path=ret_cfg,
            rerank_config_path=rerank_cfg,
            model_config_path=model_cfg,
            threshold_config_path=thresh_cfg,
            prompt_version="v1.2_controlled_rag",
            model_digest="sha256:digest",
            ollama_version="0.40.16",
            gateway_config=override_cfg,
            hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
            official=True,
        )

    # Non-official cho phép khi có đầy đủ base_model_config, runtime_overrides & effective_model_config_hash
    assert validate_run_manifest(built, official=False) == []
    assert built["base_model_config"]["num_ctx"] == 8192
    assert built["runtime_overrides"] == {"num_ctx": {"config": 8192, "runtime": 4096}}
    assert built["effective_model_config_hash"] != built["base_model_config_hash"]

    # Đối chiếu file config trực tiếp cũng chặn silent override khi thiếu override provenance
    silent_mismatch = _valid_manifest()
    from model_gateway.run_metadata import sha256_file

    silent_mismatch["config_hashes"]["model"] = sha256_file(model_cfg)
    silent_mismatch["runtime"]["num_ctx"] = 4096
    silent_errors = validate_run_manifest(silent_mismatch, official=False, model_config_path=model_cfg)
    assert any("model_config_hash_mismatch" in err and "num_ctx" in err for err in silent_errors), silent_errors


@pytest.mark.req("NFR4.1")
def test_runtime_and_manifest_reject_contradictory_cache_and_fallback_flags():
    for is_official in (True, False):
        bad_cache_manifest = _valid_manifest()
        bad_cache_manifest["runtime"]["cache_enabled"] = False
        bad_cache_manifest["runtime"]["cache"] = "ON"
        cache_errs = validate_run_manifest(bad_cache_manifest, official=is_official)
        assert any("cache" in err.lower() and "mâu thuẫn" in err.lower() for err in cache_errs), cache_errs

        bad_fb_manifest = _valid_manifest()
        bad_fb_manifest["runtime"]["fallback_locked"] = True
        bad_fb_manifest["runtime"]["fallback"] = "UNLOCKED"
        fb_errs = validate_run_manifest(bad_fb_manifest, official=is_official)
        assert any("fallback" in err.lower() and "mâu thuẫn" in err.lower() for err in fb_errs), fb_errs

        bad_cache_cfg = {**QwenGatewayConfig().model_dump(), "cache_enabled": False, "cache": "ON"}
        assert any("cache" in err.lower() for err in validate_runtime_config(bad_cache_cfg, official=is_official))

        bad_fb_cfg = {**QwenGatewayConfig().model_dump(), "fallback_locked": True, "fallback": "UNLOCKED"}
        assert any("fallback" in err.lower() for err in validate_runtime_config(bad_fb_cfg, official=is_official))


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.3")
def test_validate_runtime_config_handles_corrupt_yaml_without_raw_exception(tmp_path: Path):
    broken_yaml = tmp_path / "broken_qwen.yaml"
    broken_yaml.write_text("model: [\n", encoding="utf-8")

    errors = validate_runtime_config(broken_yaml, official=True)
    assert errors
    assert any("YAML_PARSE_ERROR" in err and str(broken_yaml) in err for err in errors), errors

    invalid_utf8 = tmp_path / "binary_qwen.yaml"
    invalid_utf8.write_bytes(b"\xff\xfe\x00\x80")
    read_errors = validate_runtime_config(invalid_utf8, official=False)
    assert any("CONFIG_READ_ERROR" in err and str(invalid_utf8) in err for err in read_errors), read_errors
