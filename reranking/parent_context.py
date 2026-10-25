"""Parent-Context Resolver (architecture: Retrieval block, after the Cross-Encoder Reranker).

Each ranked child chunk keeps its ``chunk_id``, ``rank`` and ``score`` (Strict Match
and citations still use them) and gains ``parent_id`` and ``parent_text`` from
``data/chunking_output/parents.json``. Several children of one parent share the
parent: only the best-ranked child carries ``parent_text``, the others get ``null``.
``parent_text`` is also ``null`` once the total context would exceed
``max_context_chars``, so the generator receives a bounded context.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENTS_PATH = ROOT / "data" / "chunking_output" / "parents.json"
DEFAULT_MAX_CONTEXT_CHARS = 6000
CONFIG_KEYS = ("enabled", "parents_file", "max_context_chars")


@dataclass(frozen=True)
class ParentContextConfig:
    enabled: bool = True
    parents_file: Path = DEFAULT_PARENTS_PATH
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("parent_context.enabled phải là true/false")
        if (not isinstance(self.max_context_chars, int) or isinstance(self.max_context_chars, bool)
                or self.max_context_chars < 1):
            raise ValueError("parent_context.max_context_chars phải là số nguyên lớn hơn 0")


def load_parent_context_config(path: str | Path, **overrides: Any) -> ParentContextConfig:
    """Read the ``parent_context`` section of reranking/config.yaml; unknown keys are rejected."""
    import yaml

    config_path = Path(path)
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Không đọc được cấu hình {config_path}: {exc}") from exc
    section = data.get("parent_context") or {}
    if not isinstance(section, Mapping):
        raise ValueError("parent_context phải là YAML mapping")
    unknown = sorted(set(section) - set(CONFIG_KEYS))
    if unknown:
        raise ValueError(f"Khóa lạ trong parent_context: {unknown}")
    values = {**section, **{key: value for key, value in overrides.items() if value is not None}}
    if "parents_file" in values:
        parents_file = Path(values["parents_file"])
        values["parents_file"] = parents_file if parents_file.is_absolute() else ROOT / parents_file
    return ParentContextConfig(**values)


class ParentContextResolver:
    def __init__(self, parents: Sequence[Mapping[str, Any]], *, max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
                 source: str = "in-memory"):
        self.max_context_chars = max_context_chars
        self.source = source
        self.parents: dict[str, str] = {}
        self.child_to_parent: dict[str, str] = {}
        for parent in parents:
            parent_id, text = parent.get("parent_id"), parent.get("text")
            if not isinstance(parent_id, str) or not parent_id or not isinstance(text, str):
                raise ValueError(f"Parent thiếu parent_id hoặc text: {parent!r:.120}")
            if parent_id in self.parents:
                raise ValueError(f"parent_id bị trùng: {parent_id}")
            self.parents[parent_id] = text
            for child_id in parent.get("child_ids") or []:
                self.child_to_parent[child_id] = parent_id
        self.last_stats: dict[str, int] = {}

    @classmethod
    def from_config(cls, config: ParentContextConfig) -> "ParentContextResolver":
        path = Path(config.parents_file)
        try:
            parents = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Không đọc được parents file {path}: {exc}") from exc
        if not isinstance(parents, list):
            raise ValueError(f"{path} phải là JSON list các parent")
        return cls(parents, max_context_chars=config.max_context_chars, source=str(path))

    def describe(self) -> dict[str, Any]:
        return {"parents_file": self.source, "max_context_chars": self.max_context_chars}

    def resolve(self, results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Return copies of ``results`` (already in final rank order) with parent_id/parent_text."""
        seen: set[str] = set()
        used_chars = 0
        stats = {"parents_attached": 0, "parents_shared": 0, "parents_missing": 0,
                 "parents_over_budget": 0, "upstream_parent_id_replaced": 0, "context_chars": 0}
        resolved = []
        for result in results:
            row = dict(result)
            # parents.json (child_ids) is the source of truth: index payloads may carry the
            # clause ID in parent_id (E6), so the upstream value is only a fallback.
            upstream = row.get("parent_id")
            parent_id = self.child_to_parent.get(row["chunk_id"]) or upstream
            if upstream and parent_id != upstream:
                stats["upstream_parent_id_replaced"] += 1
            row["parent_id"] = parent_id
            row["parent_text"] = None
            if parent_id is None or parent_id not in self.parents:
                stats["parents_missing"] += 1
            elif parent_id in seen:
                stats["parents_shared"] += 1
            else:
                text = self.parents[parent_id]
                if used_chars + len(text) > self.max_context_chars:
                    stats["parents_over_budget"] += 1
                else:
                    row["parent_text"] = text
                    used_chars += len(text)
                    stats["parents_attached"] += 1
                seen.add(parent_id)
            resolved.append(row)
        stats["context_chars"] = used_chars
        if stats["parents_missing"]:
            logger.warning("Parent-Context Resolver: %d kết quả không tìm thấy parent", stats["parents_missing"])
        self.last_stats = stats
        return resolved


__all__ = ["ParentContextConfig", "ParentContextResolver", "load_parent_context_config"]
