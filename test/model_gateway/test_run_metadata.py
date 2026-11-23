"""Unit tests for runtime config and model-run manifest validator (D3.4)."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, QwenGatewayConfig
from model_gateway.run_metadata import (
    CONFIG_TO_RUNTIME_FIELD_MAP,
    RUNTIME_TO_CONFIG_FIELD_MAP,
    ManifestValidationError,
    _canonical_json_sha256,
    assert_valid_run_manifest,
    build_model_run_manifest,
    collect_hardware_profile,
    sha256_file,
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
    base_cfg = QwenGatewayConfig().model_dump(mode="json")
    base_cfg_hash = _canonical_json_sha256(base_cfg)
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
            "model": sha256_file(DEFAULT_CONFIG_PATH),
            "threshold": SHA_1,
        },
        "base_model_config": base_cfg,
        "base_model_config_hash": base_cfg_hash,
        "effective_model_config_hash": base_cfg_hash,
        "runtime_overrides": {},
        "precomputed_retrieval": False,
        "precomputed_artifact": None,
        "runtime": {
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model": "qwen2.5:7b",
            "model_config_version": "local_qwen_v1.1",
            "model_digest": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
            "ollama_version": "0.40.16",
            "prompt_version": "v1.2_controlled_rag",
            "num_ctx": 8192,
            "num_predict": 1024,
            "temperature": 0.0,
            "repeat_penalty": 1.0,
            "timeout_seconds": 120.0,
            "max_retries": 1,
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
    warm_temp["runtime_overrides"] = {"temperature": {"config": 0.0, "runtime": 0.2}}
    warm_temp["effective_model_config_hash"] = _canonical_json_sha256(
        QwenGatewayConfig(temperature=0.2).model_dump(mode="json")
    )
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

    # Ghi manifest có override ra đĩa và validate độc lập từ file JSON
    manifest_json_path = tmp_path / "run_manifest.json"
    manifest_json_path.write_text(json.dumps(built), encoding="utf-8")
    disk_official_errors = validate_run_manifest(manifest_json_path, official=True)
    assert any("model_config_hash_mismatch" in err and "num_ctx" in err for err in disk_official_errors)
    assert validate_run_manifest(manifest_json_path, official=False) == []

    # Kiểm tra các tham số runtime khác ngoài num_ctx bị override đều bị chặn ở official=True
    for override_kwargs, expected_field in [
        ({"model": "qwen2.5:14b"}, "model"),
        ({"num_predict": 512}, "num_predict"),
        ({"temperature": 0.1}, "temperature"),
        ({"repeat_penalty": 1.2}, "repeat_penalty"),
        ({"timeout_seconds": 60.0}, "timeout_seconds"),
        ({"max_retries": 3}, "max_retries"),
    ]:
        ov_manifest = build_model_run_manifest(
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
            gateway_config=QwenGatewayConfig(**override_kwargs),
            hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
        )
        ov_manifest["working_tree_clean"] = True
        ov_errs = validate_run_manifest(ov_manifest, official=True)
        assert any("model_config_hash_mismatch" in err and expected_field in err for err in ov_errs), ov_errs


@pytest.mark.req("NFR4.1")
def test_runtime_and_manifest_reject_contradictory_cache_and_fallback_flags(tmp_path: Path):
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

        # Cực tính fallback_locked=True tương đương fallback_enabled=False; fallback_enabled=True là mâu thuẫn
        bad_fb_en_manifest = _valid_manifest()
        bad_fb_en_manifest["runtime"]["fallback_locked"] = True
        bad_fb_en_manifest["runtime"]["fallback_enabled"] = True
        assert any("mâu thuẫn" in err.lower() for err in validate_run_manifest(bad_fb_en_manifest, official=is_official))

        good_fb_en_manifest = _valid_manifest()
        good_fb_en_manifest["runtime"]["fallback_locked"] = True
        good_fb_en_manifest["runtime"]["fallback_enabled"] = False
        assert validate_run_manifest(good_fb_en_manifest, official=is_official) == []

        bad_cache_cfg = {**QwenGatewayConfig().model_dump(), "cache_enabled": False, "cache": "ON"}
        assert any("cache" in err.lower() for err in validate_runtime_config(bad_cache_cfg, official=is_official))

        bad_fb_cfg = {**QwenGatewayConfig().model_dump(), "fallback_locked": True, "fallback": "UNLOCKED"}
        assert any("fallback" in err.lower() for err in validate_runtime_config(bad_fb_cfg, official=is_official))

        # Khóa top-level vs lồng nhau (runtime/gateway) và chuỗi/kiểu lạ
        nested_conflict = {**QwenGatewayConfig().model_dump(), "runtime": {"cache": "ON"}}
        assert any("mâu thuẫn" in err.lower() for err in validate_runtime_config(nested_conflict, official=is_official))
        gateway_conflict = {**QwenGatewayConfig().model_dump(), "gateway": {"fallback_enabled": True}}
        assert any("mâu thuẫn" in err.lower() for err in validate_runtime_config(gateway_conflict, official=is_official))

        for bad_val_cfg in (
            {**QwenGatewayConfig().model_dump(), "cache": "MAYBE"},
            {**QwenGatewayConfig().model_dump(), "fallback": "AUTO"},
            {**QwenGatewayConfig().model_dump(), "cache_enabled": "false"},
        ):
            assert validate_runtime_config(bad_val_cfg, official=is_official)

    # YAML chứa .nan / .inf / -.inf / "NaN" / "Infinity" trên file config phải bị chặn
    base_yaml = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    for line_rep in (
        "timeout_seconds: .inf",
        "timeout_seconds: .nan",
        "repeat_penalty: .nan",
        "temperature: -.inf",
        'timeout_seconds: "Infinity"',
        'repeat_penalty: "NaN"',
    ):
        cfg_file = tmp_path / f"bad_num_{abs(hash(line_rep))}.yaml"
        field_name = line_rep.split(":")[0]
        patched = "\n".join(
            line_rep if line.startswith(f"{field_name}:") else line for line in base_yaml.splitlines()
        )
        cfg_file.write_text(patched + "\n", encoding="utf-8")
        assert validate_runtime_config(cfg_file, official=True)
        assert validate_runtime_config(cfg_file, official=False)


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.3")
def test_validate_runtime_config_handles_corrupt_yaml_without_raw_exception(tmp_path: Path):
    broken_yaml = tmp_path / "broken_qwen.yaml"
    broken_yaml.write_text("model: [\n", encoding="utf-8")

    errors = validate_runtime_config(broken_yaml, official=True)
    assert errors
    assert any("YAML_PARSE_ERROR" in err and str(broken_yaml) in err for err in errors), errors

    for edge_name, edge_content in [
        ("empty.yaml", ""),
        ("comment_only.yaml", "# only comments\n"),
        ("list_root.yaml", "- item1\n- item2\n"),
    ]:
        edge_file = tmp_path / edge_name
        edge_file.write_text(edge_content, encoding="utf-8")
        edge_errs = validate_runtime_config(edge_file, official=True)
        assert any("YAML_PARSE_ERROR" in err and str(edge_file) in err for err in edge_errs), edge_errs

    invalid_utf8 = tmp_path / "binary_qwen.yaml"
    invalid_utf8.write_bytes(b"\xff\xfe\x00\x80")
    read_errors = validate_runtime_config(invalid_utf8, official=False)
    assert any("CONFIG_READ_ERROR" in err and str(invalid_utf8) in err for err in read_errors), read_errors


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
def test_manifest_official_requires_model_config_source_when_read_standalone(tmp_path: Path):
    standalone = _valid_manifest()
    standalone["runtime"]["num_ctx"] = 4096
    for key in ("base_model_config", "base_model_config_hash", "effective_model_config_hash", "runtime_overrides"):
        standalone.pop(key, None)

    manifest_path = tmp_path / "standalone_official_missing_source.json"
    manifest_path.write_text(json.dumps(standalone), encoding="utf-8")

    errors = validate_run_manifest(manifest_path, official=True)
    assert any("missing_model_config_source" in err for err in errors), errors

    # Empty dict base_model_config cũng phải bị từ chối ở official=True
    standalone["base_model_config"] = {}
    assert any("missing_model_config_source" in err for err in validate_run_manifest(standalone, official=True))

    # Nếu truyền model_config_path hợp lệ kèm manifest không đổi, official=True chấp nhận; nếu lệch num_ctx thì chặn
    assert any(
        "model_config_hash_mismatch" in err and "num_ctx" in err
        for err in validate_run_manifest(manifest_path, official=True, model_config_path=DEFAULT_CONFIG_PATH)
    )
    standalone_valid = _valid_manifest()
    for key in ("base_model_config", "base_model_config_hash", "effective_model_config_hash", "runtime_overrides"):
        standalone_valid.pop(key, None)
    assert validate_run_manifest(standalone_valid, official=True, model_config_path=DEFAULT_CONFIG_PATH) == []


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
def test_manifest_non_official_verifies_base_hash_override_values_and_effective_hash(tmp_path: Path):
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

    built_override = build_model_run_manifest(
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
        gateway_config=QwenGatewayConfig(num_ctx=4096),
        hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
    )
    assert validate_run_manifest(built_override, official=False, model_config_path=model_cfg) == []
    assert validate_run_manifest(built_override, official=False) == []

    # 1. Khai báo sai giá trị cặp config/runtime trong runtime_overrides
    bad_override_vals = deepcopy(built_override)
    bad_override_vals["runtime_overrides"] = {"num_ctx": {"config": 123, "runtime": 456}}
    errs_vals = validate_run_manifest(bad_override_vals, official=False, model_config_path=model_cfg)
    assert any("runtime_overrides.num_ctx" in err for err in errs_vals), errs_vals

    # 2. Khai báo thừa khóa không thực sự thay đổi trong runtime_overrides
    extra_unchanged = deepcopy(built_override)
    extra_unchanged["runtime_overrides"]["temperature"] = {"config": 0.0, "runtime": 0.0}
    errs_extra = validate_run_manifest(extra_unchanged, official=False, model_config_path=model_cfg)
    assert any("temperature" in err and "runtime_overrides" in err for err in errs_extra), errs_extra

    # 3. effective_model_config_hash giả ("a" * 64)
    bad_eff_hash = deepcopy(built_override)
    bad_eff_hash["effective_model_config_hash"] = SHA_A
    errs_eff = validate_run_manifest(bad_eff_hash, official=False, model_config_path=model_cfg)
    assert any("effective_model_config_hash_mismatch" in err for err in errs_eff), errs_eff

    # 4. Thiếu base_model_config_hash khi có override
    missing_base_hash = deepcopy(built_override)
    missing_base_hash.pop("base_model_config_hash")
    errs_base = validate_run_manifest(missing_base_hash, official=False, model_config_path=model_cfg)
    assert any("base_model_config_hash" in err for err in errs_base), errs_base


@pytest.mark.req("NFR4.1")
@pytest.mark.parametrize("field", ["temperature", "repeat_penalty", "timeout_seconds"])
@pytest.mark.parametrize("huge_int", [10**1000, -(10**1000)])
def test_validator_rejects_huge_integers_without_overflow_error(field: str, huge_int: int):
    raw_cfg = QwenGatewayConfig().model_dump()
    raw_cfg[field] = huge_int
    for is_official in (True, False):
        cfg_errors = validate_runtime_config(raw_cfg, official=is_official)
        assert cfg_errors and all(isinstance(err, str) for err in cfg_errors)

        manifest = _valid_manifest()
        manifest["runtime"][field] = huge_int
        mf_errors = validate_run_manifest(manifest, official=is_official)
        assert any(field in err for err in mf_errors), mf_errors


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
def test_manifest_official_standalone_rejects_partial_snapshot_with_default_filling(tmp_path: Path):
    forged = _valid_manifest()
    forged["runtime"]["num_ctx"] = 4096
    forged["base_model_config"] = {"num_ctx": 4096}
    for key in ("base_model_config_hash", "effective_model_config_hash", "runtime_overrides"):
        forged.pop(key, None)

    forged_path = tmp_path / "forged_partial_official.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")

    errors = validate_run_manifest(forged_path, official=True)
    assert errors
    assert any("incomplete_base_model_config" in err for err in errors), errors
    assert any("missing_model_config_source" in err for err in errors), errors

    # Snapshot đầy đủ khóa nhưng thiếu base_model_config_hash hoặc effective_model_config_hash vẫn bị từ chối ở official=True
    for missing_hash_key in ("base_model_config_hash", "effective_model_config_hash"):
        missing_hash = _valid_manifest()
        missing_hash.pop(missing_hash_key)
        hash_errs = validate_run_manifest(missing_hash, official=True)
        assert any(missing_hash_key in err for err in hash_errs), hash_errs


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
@pytest.mark.parametrize(
    ("override_kwargs", "expected_override_key"),
    [
        ({"base_url": "http://127.0.0.1:11435"}, "base_url"),
        ({"config_version": "local_qwen_custom"}, "model_config_version"),
        ({"model": "qwen2.5:14b"}, "model"),
        ({"num_ctx": 4096}, "num_ctx"),
        ({"num_predict": 512}, "num_predict"),
        ({"temperature": 0.2}, "temperature"),
        ({"repeat_penalty": 1.2}, "repeat_penalty"),
        ({"timeout_seconds": 60.0}, "timeout_seconds"),
        ({"max_retries": 3}, "max_retries"),
        ({"cache_enabled": True}, "cache_enabled"),
        ({"fallback_locked": False}, "fallback_locked"),
    ],
)
def test_manifest_builder_validator_roundtrip_all_gateway_config_fields(
    tmp_path: Path,
    override_kwargs: dict,
    expected_override_key: str,
):
    assert set(CONFIG_TO_RUNTIME_FIELD_MAP) == set(QwenGatewayConfig.model_fields)
    assert set(RUNTIME_TO_CONFIG_FIELD_MAP.values()) == set(QwenGatewayConfig.model_fields)

    bench = tmp_path / "bench.json"
    corpus = tmp_path / "chunks.jsonl"
    ret_cfg = tmp_path / "ret.yaml"
    rerank_cfg = tmp_path / "rerank.yaml"
    thresh_cfg = tmp_path / "thresh.yaml"
    model_cfg = tmp_path / "model.yaml"
    for p, content in [
        (bench, "[]\n"),
        (corpus, '{"chunk_id":"c1"}\n'),
        (ret_cfg, "top_k: 50\n"),
        (rerank_cfg, "top_k: 10\n"),
        (thresh_cfg, "min_top1: 0.5\n"),
        (model_cfg, DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")),
    ]:
        p.write_text(content, encoding="utf-8")

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
        gateway_config=QwenGatewayConfig(**override_kwargs),
        hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
    )
    assert expected_override_key in built["runtime_overrides"]

    manifest_path = tmp_path / f"manifest_{expected_override_key}.json"
    manifest_path.write_text(json.dumps(built), encoding="utf-8")
    assert validate_run_manifest(manifest_path, official=False) == []
    assert validate_run_manifest(manifest_path, official=False, model_config_path=model_cfg) == []


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
def test_manifest_official_standalone_roundtrip_from_builder_passes(tmp_path: Path):
    bench = tmp_path / "bench.json"
    corpus = tmp_path / "chunks.jsonl"
    ret_cfg = tmp_path / "ret.yaml"
    rerank_cfg = tmp_path / "rerank.yaml"
    thresh_cfg = tmp_path / "thresh.yaml"
    model_cfg = tmp_path / "model.yaml"
    for p, content in [
        (bench, "[]\n"),
        (corpus, '{"chunk_id":"c1"}\n'),
        (ret_cfg, "top_k: 50\n"),
        (rerank_cfg, "top_k: 10\n"),
        (thresh_cfg, "min_top1: 0.5\n"),
        (model_cfg, DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")),
    ]:
        p.write_text(content, encoding="utf-8")

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
        hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
    )
    built["working_tree_clean"] = True

    manifest_path = tmp_path / "official_standalone.json"
    manifest_path.write_text(json.dumps(built), encoding="utf-8")
    assert validate_run_manifest(manifest_path, official=True) == []


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
def test_official_policy_allows_zero_or_one_retry_and_rejects_more(tmp_path: Path):
    for ok_retries in (0, 1):
        assert validate_runtime_config(QwenGatewayConfig(max_retries=ok_retries), official=True) == []

        manifest_ok = _valid_manifest()
        cfg_ok = QwenGatewayConfig(max_retries=ok_retries).model_dump(mode="json")
        cfg_ok_hash = _canonical_json_sha256(cfg_ok)
        manifest_ok["base_model_config"] = cfg_ok
        manifest_ok["base_model_config_hash"] = cfg_ok_hash
        manifest_ok["effective_model_config_hash"] = cfg_ok_hash
        manifest_ok["runtime"]["max_retries"] = ok_retries

        ok_path = tmp_path / f"manifest_retries_{ok_retries}.json"
        ok_path.write_text(json.dumps(manifest_ok), encoding="utf-8")
        assert validate_run_manifest(ok_path, official=True) == []

    for bad_retries in (2, 3):
        cfg_errors = validate_runtime_config(QwenGatewayConfig(max_retries=bad_retries), official=True)
        assert any("official_max_retries_exceeded" in err and "max_retries" in err for err in cfg_errors), cfg_errors

        manifest_bad = _valid_manifest()
        cfg_bad = QwenGatewayConfig(max_retries=bad_retries).model_dump(mode="json")
        cfg_bad_hash = _canonical_json_sha256(cfg_bad)
        manifest_bad["base_model_config"] = cfg_bad
        manifest_bad["base_model_config_hash"] = cfg_bad_hash
        manifest_bad["effective_model_config_hash"] = cfg_bad_hash
        manifest_bad["runtime"]["max_retries"] = bad_retries

        bad_path = tmp_path / f"manifest_retries_{bad_retries}.json"
        bad_path.write_text(json.dumps(manifest_bad), encoding="utf-8")
        mf_errors = validate_run_manifest(bad_path, official=True)
        assert any("official_max_retries_exceeded" in err and "max_retries" in err for err in mf_errors), mf_errors

        # Non-official giữ nguyên cho phép max_retries >= 0
        assert validate_run_manifest(bad_path, official=False) == []
        assert validate_runtime_config(QwenGatewayConfig(max_retries=bad_retries), official=False) == []


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
def test_official_manifest_blocks_extra_scopes_and_unapproved_base_config(tmp_path: Path):
    base_bad_cfg = QwenGatewayConfig(cache_enabled=True, fallback_locked=False).model_dump(mode="json")
    cfg_path = tmp_path / "bad_official_cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(base_bad_cfg, sort_keys=False), encoding="utf-8")

    manifest = _valid_manifest()
    manifest["config_hashes"]["model"] = sha256_file(cfg_path)
    manifest["base_model_config"] = base_bad_cfg
    bad_hash = _canonical_json_sha256(base_bad_cfg)
    manifest["base_model_config_hash"] = bad_hash
    manifest["effective_model_config_hash"] = bad_hash
    # Cache/fallback được đặt ở top-level trong khi runtime giữ bản mặc định -> không thể bypass official policy
    manifest["runtime"].pop("cache_enabled", None)
    manifest["runtime"].pop("cache", None)
    manifest["runtime"].pop("fallback_locked", None)
    manifest["runtime"].pop("fallback", None)
    manifest["cache"] = "OFF"
    manifest["fallback"] = "LOCKED"

    errors = validate_run_manifest(manifest, official=True, model_config_path=cfg_path)
    assert errors, "Official run phải từ chối cấu hình gốc bật cache / mở khóa fallback dù extra_scopes ghi OFF/LOCKED"
    assert any("cache_enabled" in err or "fallback_locked" in err for err in errors), errors

    # extra_scopes ở top-level chứa cache='ON' dù runtime tắt phải bị phát hiện mâu thuẫn khi tái dựng hash
    manifest_good_cfg = _valid_manifest()
    manifest_good_cfg["runtime"].pop("cache_enabled", None)
    manifest_good_cfg["runtime"].pop("cache", None)
    manifest_good_cfg["gateway"] = {"cache_enabled": True}
    errors_scope = validate_run_manifest(manifest_good_cfg, official=True)
    assert errors_scope
    assert any("cache" in err.lower() for err in errors_scope), errors_scope


@pytest.mark.req("NFR4.1")
@pytest.mark.req("NFR4.2")
def test_manifest_and_builder_handle_boundary_inputs_without_raw_exceptions(tmp_path: Path):
    huge = 10**5000

    # Extreme ISO timestamp, invalid URLs, wrong model_config_path type, huge ints
    bad = _valid_manifest()
    bad["started_at"] = "9999-12-31T23:59:59-05:00"
    bad["finished_at"] = "0001-01-01T00:00:00+05:00"
    bad["runtime"]["num_ctx"] = huge
    bad["runtime"]["max_retries"] = huge
    bad["runtime"]["base_url"] = "http://"
    bad["runtime_overrides"] = {"num_ctx": {"config": 8192, "runtime": huge}}

    errors = validate_run_manifest(bad, official=True, model_config_path=123)  # type: ignore[arg-type]
    assert any("started_at" in err for err in errors)
    assert any("finished_at" in err for err in errors)
    assert any("num_ctx" in err for err in errors)
    assert any("max_retries" in err for err in errors)
    assert any("base_url" in err for err in errors)
    assert any("model_config_path" in err for err in errors)

    ipv6_bad = _valid_manifest()
    ipv6_bad["runtime"]["base_url"] = "http://[::1"
    assert any("base_url" in err for err in validate_run_manifest(ipv6_bad, official=False))

    rt_errors = validate_runtime_config(
        {**QwenGatewayConfig().model_dump(), "max_retries": huge, "base_url": "http://"},
        official=True,
    )
    assert rt_errors

    # Directory passed as precomputed_artifact_path must not raise IsADirectoryError
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("ok", encoding="utf-8")
    dir_path = tmp_path / "artifact_dir"
    dir_path.mkdir()
    built = build_model_run_manifest(
        benchmark_path=dummy_file,
        dataset_ids=["q1"],
        corpus_path=dummy_file,
        retrieval_config_path=dummy_file,
        rerank_config_path=dummy_file,
        model_config_path=DEFAULT_CONFIG_PATH,
        threshold_config_path=dummy_file,
        prompt_version="v1.2_controlled_rag",
        model_digest="a" * 64,
        ollama_version="0.40.16",
        precomputed_artifact_path=dir_path,
        hardware={"os": "Linux", "cpu": "x86_64", "gpu": "none", "vram": "none"},
    )
    assert built["precomputed_artifact"] == {"path": dir_path.as_posix(), "status": "missing", "sha256": None}
