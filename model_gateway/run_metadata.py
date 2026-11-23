"""
model_gateway/run_metadata.py
Runtime config & model-run manifest validator for reproducibility (NFR4.1-NFR4.3, NFR2.3).
Does not duplicate canonical API/pipeline schemas in schemas/models.py.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def _read_cache_disabled(mapping: Mapping[str, Any]) -> tuple[bool | None, str | None]:
    if "cache_enabled" in mapping:
        val = mapping["cache_enabled"]
        if type(val) is bool:
            return (val is False), None
        return None, "runtime.cache_enabled phải là boolean"
    if "cache" in mapping:
        val = mapping["cache"]
        if isinstance(val, str) and val.strip().upper() in ("OFF", "ON"):
            return (val.strip().upper() == "OFF"), None
        return None, "runtime.cache phải là 'OFF' hoặc 'ON'"
    return None, "Thiếu trường trạng thái cache (runtime.cache_enabled hoặc runtime.cache)"


def _read_fallback_locked(mapping: Mapping[str, Any]) -> tuple[bool | None, str | None]:
    if "fallback_locked" in mapping:
        val = mapping["fallback_locked"]
        if type(val) is bool:
            return (val is True), None
        return None, "runtime.fallback_locked phải là boolean"
    if "fallback" in mapping:
        val = mapping["fallback"]
        if isinstance(val, str) and val.strip().upper() in ("LOCKED", "UNLOCKED"):
            return (val.strip().upper() == "LOCKED"), None
        return None, "runtime.fallback phải là 'LOCKED' hoặc 'UNLOCKED'"
    return None, "Thiếu trường khóa fallback (runtime.fallback_locked hoặc runtime.fallback)"


def validate_runtime_config(
    config: QwenGatewayConfig | Mapping[str, Any] | str | Path,
    *,
    official: bool = False,
) -> list[str]:
    """Validate runtime gateway config completeness, types and official-run invariants."""
    errors: list[str] = []
    data: dict[str, Any]
    if isinstance(config, (str, Path)):
        import yaml

        path = Path(config)
        if not path.exists():
            return [f"config_path không tồn tại: {path}"]
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return [f"config_path không phải mapping YAML hợp lệ: {path}"]
        data = loaded
    elif isinstance(config, QwenGatewayConfig):
        data = config.model_dump()
    elif isinstance(config, Mapping):
        data = dict(config)
    else:
        return [f"config phải là QwenGatewayConfig, Mapping hoặc đường dẫn file, nhận được {type(config).__name__}"]

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
        if isinstance(temp, bool) or not isinstance(temp, (int, float)) or not 0.0 <= float(temp) <= 2.0:
            errors.append("runtime.temperature phải là số thực trong [0.0, 2.0]")
        elif official and float(temp) != 0.0:
            errors.append(f"Official run yêu cầu runtime.temperature == 0, nhận được {temp}")

        penalty = runtime.get("repeat_penalty")
        if isinstance(penalty, bool) or not isinstance(penalty, (int, float)) or float(penalty) <= 0.0:
            errors.append("runtime.repeat_penalty phải là số thực > 0")

        cache_off, cache_err = _read_cache_disabled(runtime)
        if cache_err:
            errors.append(cache_err)
        elif official and cache_off is not True:
            errors.append("Official run yêu cầu cache phải tắt (cache_enabled=False / cache='OFF')")

        fallback_locked, fb_err = _read_fallback_locked(runtime)
        if fb_err:
            errors.append(fb_err)
        elif official and fallback_locked is not True:
            errors.append("Official run yêu cầu fallback phải khóa (fallback_locked=True / fallback='LOCKED')")

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
) -> dict[str, Any]:
    """Validate manifest and raise ManifestValidationError with explicit field list on failure."""
    errors = validate_run_manifest(manifest, official=official)
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
) -> dict[str, Any]:
    """Build a complete NFR4.2/NFR2.3-compliant model run manifest without fabricating missing fields."""
    cfg = gateway_config or QwenGateway.load_config(model_config_path)
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

    return {
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
            "cache": "OFF" if not cfg.cache_enabled else "ON",
            "cache_enabled": cfg.cache_enabled,
            "fallback": "LOCKED" if cfg.fallback_locked else "UNLOCKED",
            "fallback_locked": cfg.fallback_locked,
        },
        "hardware": hw,
        "started_at": started_at or now_utc,
        "finished_at": finished_at or now_utc,
    }
