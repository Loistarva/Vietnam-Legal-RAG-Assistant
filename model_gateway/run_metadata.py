"""
model_gateway/run_metadata.py
Runtime config & model-run manifest validator for reproducibility (NFR4.1-NFR4.3, NFR2.3).
Does not duplicate canonical API/pipeline schemas in schemas/models.py.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH, REQUIRED_CONFIG_KEYS, QwenGateway, QwenGatewayConfig

_HEX_64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

REQUIRED_CONFIG_HASH_KEYS: tuple[str, ...] = ("retrieval", "rerank", "model", "threshold")
REQUIRED_HARDWARE_KEYS: tuple[str, ...] = ("os", "cpu", "gpu", "vram")
REQUIRED_RUNTIME_MANIFEST_KEYS: tuple[str, ...] = (
    "model",
    "model_digest",
    "ollama_version",
    "prompt_version",
    "num_ctx",
    "num_predict",
    "temperature",
    "repeat_penalty",
)


class ManifestValidationError(ValueError):
    """Raised when runtime config or run_manifest.json fails NFR4 validation."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("Kiểm tra runtime/manifest thất bại: " + "; ".join(self.errors))


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def _canonical_json_sha256(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_yaml_mapping(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists() or path.is_dir():
        return None, f"CONFIG_READ_ERROR: file_path={path} không tồn tại hoặc không phải tệp"
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"CONFIG_READ_ERROR: file_path={path} ({type(exc).__name__}: {exc})"
    try:
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        loc = f" line={mark.line + 1}, column={mark.column + 1}" if mark is not None else ""
        return None, f"YAML_PARSE_ERROR: file_path={path}{loc} ({type(exc).__name__}: {exc})"
    if not isinstance(loaded, dict):
        return None, f"YAML_PARSE_ERROR: file_path={path} không phải mapping YAML hợp lệ"
    return loaded, None


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    cleaned = value.strip()
    if cleaned.startswith("sha256:"):
        cleaned = cleaned.removeprefix("sha256:")
    return bool(_HEX_64_RE.match(cleaned))


def _parse_utc_iso(value: Any) -> datetime | None:
    if not _is_non_empty_str(value):
        return None
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def sha256_file(path: str | Path) -> str:
    """Compute platform-consistent SHA-256 on LF-normalized UTF-8 text or raw bytes."""
    file_path = Path(path)
    raw = file_path.read_bytes()
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeDecodeError:
        return hashlib.sha256(raw).hexdigest()


def collect_git_state(repo_root: str | Path | None = None) -> dict[str, Any]:
    """Collect current git branch, commit SHA and working_tree_clean flag."""
    cwd = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return {
            "git_branch": branch or "HEAD",
            "git_sha": sha,
            "working_tree_clean": not bool(dirty),
        }
    except (OSError, subprocess.CalledProcessError):
        return {
            "git_branch": "",
            "git_sha": "",
            "working_tree_clean": False,
        }


def collect_hardware_profile() -> dict[str, str]:
    """Collect host OS, CPU, GPU and VRAM information for NFR2.3 manifest tracking."""
    gpu_name = "none"
    vram = "none"
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if lines:
            parts = [part.strip() for part in lines[0].split(",")]
            gpu_name = parts[0] if parts else "unknown"
            vram = f"{parts[1]} MiB" if len(parts) > 1 and parts[1] else "unknown"
    except (OSError, subprocess.SubprocessError, TimeoutError):
        pass

    cpu = platform.processor().strip() or platform.machine().strip() or "unknown"
    return {
        "os": platform.platform(),
        "cpu": cpu,
        "gpu": gpu_name,
        "vram": vram,
    }


def _parse_bool_flag(mapping: Mapping[str, Any], key: str, prefix: str) -> tuple[bool | None, str | None]:
    val = mapping[key]
    if type(val) is not bool:
        return None, f"{prefix}{key} phải là boolean"
    return val, None


def _parse_str_flag(
    mapping: Mapping[str, Any],
    key: str,
    prefix: str,
    true_token: str,
    false_token: str,
) -> tuple[bool | None, str | None]:
    val = mapping[key]
    if not isinstance(val, str) or val.strip().upper() not in (true_token, false_token):
        return None, f"{prefix}{key} phải là '{true_token}' hoặc '{false_token}'"
    return val.strip().upper() == true_token, None


def _read_cache_disabled(
    mapping: Mapping[str, Any],
    *,
    prefix: str = "runtime.",
    extra_scopes: Sequence[tuple[str, Mapping[str, Any]]] = (),
) -> tuple[bool | None, str | None]:
    parsed: list[tuple[str, bool]] = []
    for scope_prefix, scope in [(prefix, mapping), *extra_scopes]:
        if "cache_enabled" in scope:
            val, err = _parse_bool_flag(scope, "cache_enabled", scope_prefix)
            if err:
                return None, err
            assert val is not None
            parsed.append((f"{scope_prefix}cache_enabled", val is False))
        if "cache" in scope:
            val, err = _parse_str_flag(scope, "cache", scope_prefix, "OFF", "ON")
            if err:
                return None, err
            assert val is not None
            parsed.append((f"{scope_prefix}cache", val))
    if not parsed:
        return None, f"Thiếu trường trạng thái cache ({prefix}cache_enabled hoặc {prefix}cache)"
    if len({state for _, state in parsed}) > 1:
        names = ", ".join(name for name, _ in parsed)
        return None, f"Mâu thuẫn trạng thái cache giữa các trường: {names}"
    return parsed[0][1], None


def _read_fallback_locked(
    mapping: Mapping[str, Any],
    *,
    prefix: str = "runtime.",
    extra_scopes: Sequence[tuple[str, Mapping[str, Any]]] = (),
) -> tuple[bool | None, str | None]:
    parsed: list[tuple[str, bool]] = []
    for scope_prefix, scope in [(prefix, mapping), *extra_scopes]:
        if "fallback_locked" in scope:
            val, err = _parse_bool_flag(scope, "fallback_locked", scope_prefix)
            if err:
                return None, err
            assert val is not None
            parsed.append((f"{scope_prefix}fallback_locked", val is True))
        if "fallback_enabled" in scope:
            val, err = _parse_bool_flag(scope, "fallback_enabled", scope_prefix)
            if err:
                return None, err
            assert val is not None
            parsed.append((f"{scope_prefix}fallback_enabled", val is False))
        if "fallback" in scope:
            val, err = _parse_str_flag(scope, "fallback", scope_prefix, "LOCKED", "UNLOCKED")
            if err:
                return None, err
            assert val is not None
            parsed.append((f"{scope_prefix}fallback", val))
    if not parsed:
        return None, f"Thiếu trường khóa fallback ({prefix}fallback_locked hoặc {prefix}fallback)"
    if len({state for _, state in parsed}) > 1:
        names = ", ".join(name for name, _ in parsed)
        return None, f"Mâu thuẫn trạng thái fallback giữa các trường: {names}"
    return parsed[0][1], None


def _compare_runtime_with_model_config(
    runtime: Mapping[str, Any],
    base_cfg: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return fields where runtime parameters diverge from the hashed model config."""
    mismatches: dict[str, dict[str, Any]] = {}
    for rt_key, cfg_key in (
        ("provider", "provider"),
        ("model", "model"),
        ("model_config_version", "config_version"),
        ("num_ctx", "num_ctx"),
        ("num_predict", "num_predict"),
        ("max_retries", "max_retries"),
    ):
        if rt_key in runtime and cfg_key in base_cfg and runtime[rt_key] != base_cfg[cfg_key]:
            mismatches[rt_key] = {"config": base_cfg[cfg_key], "runtime": runtime[rt_key]}

    for float_key in ("temperature", "repeat_penalty", "timeout_seconds"):
        if (
            float_key in runtime
            and float_key in base_cfg
            and _is_finite_number(runtime[float_key])
            and _is_finite_number(base_cfg[float_key])
            and float(runtime[float_key]) != float(base_cfg[float_key])
        ):
            mismatches[float_key] = {"config": base_cfg[float_key], "runtime": runtime[float_key]}

    cache_off, cache_err = _read_cache_disabled(runtime, prefix="runtime.")
    if cache_err is None and cache_off is not None and "cache_enabled" in base_cfg:
        rt_cache_enabled = not cache_off
        if rt_cache_enabled != bool(base_cfg["cache_enabled"]):
            mismatches["cache_enabled"] = {"config": bool(base_cfg["cache_enabled"]), "runtime": rt_cache_enabled}

    fb_locked, fb_err = _read_fallback_locked(runtime, prefix="runtime.")
    if fb_err is None and fb_locked is not None and "fallback_locked" in base_cfg:
        if fb_locked != bool(base_cfg["fallback_locked"]):
            mismatches["fallback_locked"] = {"config": bool(base_cfg["fallback_locked"]), "runtime": fb_locked}

    return mismatches


def validate_runtime_config(
    config: QwenGatewayConfig | Mapping[str, Any] | str | Path,
    *,
    official: bool = False,
) -> list[str]:
    """Validate runtime gateway config completeness, types and official-run invariants."""
    errors: list[str] = []
    data: dict[str, Any]
    if isinstance(config, (str, Path)):
        path = Path(config)
        loaded, load_err = _load_yaml_mapping(path)
        if load_err is not None or loaded is None:
            return [load_err or f"CONFIG_READ_ERROR: file_path={path}"]
        data = loaded
    elif isinstance(config, QwenGatewayConfig):
        data = config.model_dump()
    elif isinstance(config, Mapping):
        data = dict(config)
    else:
        return [f"config phải là QwenGatewayConfig, Mapping hoặc đường dẫn file, nhận được {type(config).__name__}"]

    extra_scopes = [
        (f"{key}.", data[key])
        for key in ("runtime", "gateway", "model_gateway")
        if isinstance(data.get(key), Mapping)
    ]
    if any("cache_enabled" in scope or "cache" in scope for _, scope in [("", data), *extra_scopes]):
        _, cache_err = _read_cache_disabled(data, prefix="", extra_scopes=extra_scopes)
        if cache_err:
            errors.append(cache_err)
    if any(
        "fallback_locked" in scope or "fallback_enabled" in scope or "fallback" in scope
        for _, scope in [("", data), *extra_scopes]
    ):
        _, fb_err = _read_fallback_locked(data, prefix="", extra_scopes=extra_scopes)
        if fb_err:
            errors.append(fb_err)

    for key in REQUIRED_CONFIG_KEYS:
        if key not in data:
            errors.append(f"Thiếu khóa bắt buộc trong runtime config: {key}")

    if errors:
        return errors

    try:
        parsed = QwenGatewayConfig(**data)
    except Exception as exc:
        return [f"Cấu hình runtime không hợp lệ: {exc}"]

    if official:
        if parsed.temperature != 0.0:
            errors.append(f"Official run yêu cầu temperature == 0.0, nhận được {parsed.temperature}")
        if parsed.cache_enabled is not False:
            errors.append(f"Official run yêu cầu cache_enabled == False, nhận được {parsed.cache_enabled}")
        if parsed.fallback_locked is not True:
            errors.append(f"Official run yêu cầu fallback_locked == True, nhận được {parsed.fallback_locked}")

    return errors


def validate_run_manifest(
    manifest: Mapping[str, Any] | str | Path,
    *,
    official: bool = False,
    model_config_path: str | Path | None = None,
) -> list[str]:
    """Validate model-run manifest against NFR4.1, NFR4.2, NFR4.3 and NFR2.3."""
    if isinstance(manifest, (str, Path)):
        path = Path(manifest)
        if not path.exists():
            return [f"manifest_path không tồn tại: {path}"]
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return [f"manifest_path không đọc được JSON hợp lệ ({path}): {exc}"]
        if not isinstance(loaded, dict):
            return [f"manifest phải là JSON object: {path}"]
        data: Mapping[str, Any] = loaded
    elif isinstance(manifest, Mapping):
        data = manifest
    else:
        return [f"manifest phải là Mapping hoặc đường dẫn file, nhận được {type(manifest).__name__}"]

    errors: list[str] = []

    # 1. Git & working tree
    if not _is_non_empty_str(data.get("git_branch")):
        errors.append("Thiếu hoặc rỗng trường bắt buộc: git_branch")
    git_sha = data.get("git_sha")
    if not _is_non_empty_str(git_sha) or not _GIT_SHA_RE.match(str(git_sha).strip()):
        errors.append("Thiếu hoặc sai định dạng commit SHA: git_sha")

    clean = data.get("working_tree_clean")
    if type(clean) is not bool:
        errors.append("Thiếu hoặc sai kiểu boolean: working_tree_clean")
    elif official and clean is not True:
        errors.append("Official run yêu cầu working_tree_clean == True")

    # 2. Data & config hashes (NFR4.2, NFR4.3)
    for hash_key in ("benchmark_sha256", "dataset_ids_hash", "corpus_hash"):
        if not _is_sha256(data.get(hash_key)):
            errors.append(f"Thiếu hoặc sai định dạng SHA-256: {hash_key}")

    config_hashes = data.get("config_hashes")
    if not isinstance(config_hashes, Mapping):
        errors.append("Thiếu hoặc sai kiểu object: config_hashes")
    else:
        for key in REQUIRED_CONFIG_HASH_KEYS:
            if not _is_sha256(config_hashes.get(key)):
                errors.append(f"Thiếu hoặc sai định dạng SHA-256: config_hashes.{key}")

    # 3. Precomputed artifact state
    precomputed = data.get("precomputed_retrieval")
    if type(precomputed) is not bool:
        errors.append("Thiếu hoặc sai kiểu boolean: precomputed_retrieval")
    elif precomputed is True:
        artifact = data.get("precomputed_artifact")
        if not isinstance(artifact, Mapping):
            errors.append("precomputed_retrieval=True yêu cầu object precomputed_artifact")
        else:
            if not _is_non_empty_str(artifact.get("path")) and not _is_non_empty_str(artifact.get("status")):
                errors.append("precomputed_artifact thiếu trường 'path' hoặc 'status'")
            if not _is_sha256(artifact.get("sha256")):
                errors.append("precomputed_artifact thiếu hoặc sai định dạng 'sha256'")

    # 4. Runtime & model provenance
    runtime = data.get("runtime")
    if not isinstance(runtime, Mapping):
        errors.append("Thiếu hoặc sai kiểu object: runtime")
    else:
        for str_key in ("model", "model_digest", "ollama_version", "prompt_version"):
            if not _is_non_empty_str(runtime.get(str_key)):
                errors.append(f"Thiếu hoặc rỗng trường bắt buộc: runtime.{str_key}")

        for int_key in ("num_ctx", "num_predict"):
            val = runtime.get(int_key)
            if type(val) is not int or val <= 0:
                errors.append(f"runtime.{int_key} phải là số nguyên dương (> 0)")

        temp = runtime.get("temperature")
        if not _is_finite_number(temp) or not 0.0 <= float(temp) <= 2.0:
            errors.append("runtime.temperature phải là số thực hữu hạn trong [0.0, 2.0]")
        elif official and float(temp) != 0.0:
            errors.append(f"Official run yêu cầu runtime.temperature == 0, nhận được {temp}")

        penalty = runtime.get("repeat_penalty")
        if not _is_finite_number(penalty) or float(penalty) <= 0.0:
            errors.append("runtime.repeat_penalty phải là số thực hữu hạn > 0")

        if "max_retries" in runtime:
            retries_val = runtime.get("max_retries")
            if type(retries_val) is not int or retries_val < 0:
                errors.append("runtime.max_retries phải là số nguyên không âm (>= 0)")

        if "timeout_seconds" in runtime:
            timeout_val = runtime.get("timeout_seconds")
            if not _is_finite_number(timeout_val) or float(timeout_val) <= 0.0:
                errors.append("runtime.timeout_seconds phải là số thực hữu hạn > 0")

        manifest_extra_scopes = [("", data)] + [
            (f"{key}.", data[key])
            for key in ("gateway", "model_gateway")
            if isinstance(data.get(key), Mapping)
        ]
        cache_off, cache_err = _read_cache_disabled(runtime, prefix="runtime.", extra_scopes=manifest_extra_scopes)
        if cache_err:
            errors.append(cache_err)
        elif official and cache_off is not True:
            errors.append("Official run yêu cầu cache phải tắt (cache_enabled=False / cache='OFF')")

        fallback_locked, fb_err = _read_fallback_locked(
            runtime, prefix="runtime.", extra_scopes=manifest_extra_scopes
        )
        if fb_err:
            errors.append(fb_err)
        elif official and fallback_locked is not True:
            errors.append("Official run yêu cầu fallback phải khóa (fallback_locked=True / fallback='LOCKED')")

        # 4b. Đối chiếu model config đã băm với cấu hình runtime hiệu lực
        runtime_mismatches: dict[str, dict[str, Any]] = {}
        if model_config_path is not None:
            cfg_path = Path(model_config_path)
            loaded_cfg, load_err = _load_yaml_mapping(cfg_path)
            if load_err is not None or loaded_cfg is None:
                errors.append(load_err or f"CONFIG_READ_ERROR: file_path={cfg_path}")
            else:
                if isinstance(config_hashes, Mapping) and _is_sha256(config_hashes.get("model")):
                    if sha256_file(cfg_path) != str(config_hashes["model"]).removeprefix("sha256:"):
                        errors.append(
                            f"model_config_hash_mismatch: config_hashes.model không khớp SHA-256 của {cfg_path}"
                        )
                try:
                    parsed_file_cfg = QwenGatewayConfig(**loaded_cfg)
                except Exception as exc:
                    errors.append(f"model_config_hash_mismatch: file config {cfg_path} không hợp lệ ({exc})")
                else:
                    runtime_mismatches.update(
                        _compare_runtime_with_model_config(runtime, parsed_file_cfg.model_dump(mode="json"))
                    )

        base_model_cfg = data.get("base_model_config")
        if base_model_cfg is not None:
            if not isinstance(base_model_cfg, Mapping):
                errors.append("base_model_config phải là object")
            else:
                runtime_mismatches.update(_compare_runtime_with_model_config(runtime, base_model_cfg))

        declared_overrides = data.get("runtime_overrides")
        if declared_overrides is not None and not isinstance(declared_overrides, Mapping):
            errors.append("runtime_overrides phải là object")

        base_hash = data.get("base_model_config_hash")
        eff_hash = data.get("effective_model_config_hash")
        if base_hash is not None and not _is_sha256(base_hash):
            errors.append("Sai định dạng SHA-256: base_model_config_hash")
        if eff_hash is not None and not _is_sha256(eff_hash):
            errors.append("Sai định dạng SHA-256: effective_model_config_hash")
        if isinstance(base_model_cfg, Mapping) and _is_sha256(base_hash):
            if _canonical_json_sha256(dict(base_model_cfg)) != str(base_hash).removeprefix("sha256:"):
                errors.append("model_config_hash_mismatch: base_model_config không khớp base_model_config_hash")

        all_override_fields = set(runtime_mismatches.keys())
        if isinstance(declared_overrides, Mapping):
            all_override_fields.update(str(k) for k in declared_overrides.keys())
        hash_diverged = bool(base_hash and eff_hash and base_hash != eff_hash)

        if official and (all_override_fields or hash_diverged):
            field_list = ", ".join(sorted(all_override_fields)) or "effective_model_config_hash"
            errors.append(
                f"model_config_hash_mismatch: official run không cho phép override runtime khác file model config ({field_list})"
            )
        elif not official and runtime_mismatches:
            has_eff_hash = _is_sha256(eff_hash)
            has_base = isinstance(base_model_cfg, Mapping)
            covered_fields = set(declared_overrides.keys()) if isinstance(declared_overrides, Mapping) else set()
            uncovered = set(runtime_mismatches.keys()) - covered_fields
            same_hash_on_mismatch = bool(base_hash and eff_hash and base_hash == eff_hash)
            if not (has_eff_hash and has_base and isinstance(declared_overrides, Mapping)) or uncovered or same_hash_on_mismatch:
                missing_str = ", ".join(sorted(uncovered or runtime_mismatches.keys()))
                errors.append(
                    f"model_config_hash_mismatch: runtime lệch khỏi model config ({missing_str}) "
                    "nhưng thiếu base_model_config / runtime_overrides / effective_model_config_hash hợp lệ"
                )

    # 5. Hardware profile (NFR2.3)
    hardware = data.get("hardware")
    if not isinstance(hardware, Mapping):
        errors.append("Thiếu hoặc sai kiểu object: hardware")
    else:
        for hw_key in REQUIRED_HARDWARE_KEYS:
            if not _is_non_empty_str(hardware.get(hw_key)):
                errors.append(f"Thiếu hoặc rỗng trường bắt buộc: hardware.{hw_key}")

    # 6. Execution timestamps (UTC ISO-8601)
    started = _parse_utc_iso(data.get("started_at"))
    finished = _parse_utc_iso(data.get("finished_at"))
    if started is None:
        errors.append("Thiếu hoặc sai định dạng ISO-8601 UTC: started_at")
    if finished is None:
        errors.append("Thiếu hoặc sai định dạng ISO-8601 UTC: finished_at")
    if started is not None and finished is not None and finished < started:
        errors.append("finished_at không được nhỏ hơn started_at")

    return errors


def assert_valid_run_manifest(
    manifest: Mapping[str, Any] | str | Path,
    *,
    official: bool = False,
    model_config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate manifest and raise ManifestValidationError with explicit field list on failure."""
    errors = validate_run_manifest(manifest, official=official, model_config_path=model_config_path)
    if errors:
        raise ManifestValidationError(errors)
    if isinstance(manifest, (str, Path)):
        return json.loads(Path(manifest).read_text(encoding="utf-8"))
    return dict(manifest)


def build_model_run_manifest(
    *,
    benchmark_path: str | Path,
    dataset_ids: Sequence[str],
    corpus_path: str | Path,
    retrieval_config_path: str | Path,
    rerank_config_path: str | Path,
    model_config_path: str | Path = DEFAULT_CONFIG_PATH,
    threshold_config_path: str | Path,
    prompt_version: str,
    model_digest: str | None,
    ollama_version: str | None,
    started_at: str | None = None,
    finished_at: str | None = None,
    precomputed_artifact_path: str | Path | None = None,
    repo_root: str | Path | None = None,
    gateway_config: QwenGatewayConfig | None = None,
    hardware: dict[str, str] | None = None,
    official: bool = False,
) -> dict[str, Any]:
    """Build a complete NFR4.2/NFR2.3-compliant model run manifest without fabricating missing fields."""
    file_cfg = QwenGateway.load_config(model_config_path)
    cfg = gateway_config or file_cfg
    file_cfg_dump = file_cfg.model_dump(mode="json")
    eff_cfg_dump = cfg.model_dump(mode="json")
    runtime_overrides = {
        field: {"config": file_cfg_dump[field], "runtime": eff_cfg_dump[field]}
        for field in eff_cfg_dump
        if file_cfg_dump.get(field) != eff_cfg_dump[field]
    }
    base_model_config_hash = _canonical_json_sha256(file_cfg_dump)
    effective_model_config_hash = _canonical_json_sha256(eff_cfg_dump)

    git_state = collect_git_state(repo_root)
    hw = hardware or collect_hardware_profile()
    ids_bytes = (json.dumps(list(dataset_ids), ensure_ascii=False) + "\n").encode("utf-8")
    now_utc = datetime.now(timezone.utc).isoformat()

    precomputed_artifact: dict[str, Any] | None = None
    if precomputed_artifact_path is not None:
        art_path = Path(precomputed_artifact_path)
        precomputed_artifact = {
            "path": art_path.as_posix(),
            "status": "present" if art_path.exists() else "missing",
            "sha256": sha256_file(art_path) if art_path.exists() else None,
        }

    manifest: dict[str, Any] = {
        "manifest_version": "d3.4.run_manifest.v1",
        **git_state,
        "benchmark_sha256": sha256_file(benchmark_path),
        "dataset_ids_hash": hashlib.sha256(ids_bytes).hexdigest(),
        "corpus_hash": sha256_file(corpus_path),
        "config_hashes": {
            "retrieval": sha256_file(retrieval_config_path),
            "rerank": sha256_file(rerank_config_path),
            "model": sha256_file(model_config_path),
            "threshold": sha256_file(threshold_config_path),
        },
        "base_model_config": file_cfg_dump,
        "base_model_config_hash": base_model_config_hash,
        "effective_model_config_hash": effective_model_config_hash,
        "runtime_overrides": runtime_overrides,
        "precomputed_retrieval": precomputed_artifact_path is not None,
        "precomputed_artifact": precomputed_artifact,
        "runtime": {
            "provider": cfg.provider,
            "model": cfg.model,
            "model_config_version": cfg.config_version,
            "model_digest": model_digest,
            "ollama_version": ollama_version,
            "prompt_version": prompt_version,
            "num_ctx": cfg.num_ctx,
            "num_predict": cfg.num_predict,
            "temperature": cfg.temperature,
            "repeat_penalty": cfg.repeat_penalty,
            "timeout_seconds": cfg.timeout_seconds,
            "max_retries": cfg.max_retries,
            "cache": "OFF" if not cfg.cache_enabled else "ON",
            "cache_enabled": cfg.cache_enabled,
            "fallback": "LOCKED" if cfg.fallback_locked else "UNLOCKED",
            "fallback_locked": cfg.fallback_locked,
        },
        "hardware": hw,
        "started_at": started_at or now_utc,
        "finished_at": finished_at or now_utc,
    }
    if official:
        assert_valid_run_manifest(manifest, official=True, model_config_path=model_config_path)
    return manifest
