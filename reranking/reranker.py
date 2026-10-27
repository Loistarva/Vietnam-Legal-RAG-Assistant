"""Reranking for Hybrid retrieval candidates (Sprint 6, Dev 5).

``Reranker.rerank(query, hits, top_k)`` implements the ``Reranker`` protocol of
``retrieval.hybrid_retriever`` and only reorders candidates: every input field
(chunk_id, chunk_text, parent_clause_id, document_id, metadata.validity_status,
...) is copied through, ``rank``/``score`` are replaced by the rerank output and
the incoming values are kept as ``retrieval_rank``/``retrieval_score``.

Reranker scores have their own scale; never compare them with BM25, dense or
RRF scores.
"""
from __future__ import annotations

import copy
import logging
import math
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Protocol, Sequence

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")
DEFAULT_MODEL_NAME = "BAAI/bge-reranker-v2-m3"
BACKENDS = ("mock", "cross_encoder")
# Text given to the scorer: the cited chunk alone, or prefixed with its breadcrumb
# (Chương > Điều > Khoản), since many child chunks start with "2. ..." and lack the article name.
CANDIDATE_TEXT_MODES = ("chunk_text", "breadcrumb_chunk_text")
# Weights of the cross-encoder. auto: float16 on CUDA (bge-reranker-v2-m3 needs about 1.1 GB
# instead of 2.2 GB, so it fits a 4 GB GPU next to the dense model), float32 on CPU.
DTYPES = ("auto", "float32", "float16", "bfloat16")

_TOKEN_PATTERN = re.compile(r"\w+")


def _require_positive_int(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} phải là số nguyên lớn hơn 0")
    return value


@dataclass(frozen=True)
class RerankerConfig:
    """Values of the ``reranker`` section in ``reranking/config.yaml``."""

    enabled: bool = True
    backend: str = "mock"
    model: str = DEFAULT_MODEL_NAME
    rerank_top_k: int = 5
    max_candidates: int = 50
    batch_size: int = 16
    max_length: int = 512
    device: str | None = None
    dtype: str = "auto"
    candidate_text: str = "chunk_text"

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled phải là true/false")
        if self.backend not in BACKENDS:
            raise ValueError(f"backend phải thuộc {BACKENDS}, nhận được {self.backend!r}")
        if self.candidate_text not in CANDIDATE_TEXT_MODES:
            raise ValueError(f"candidate_text phải thuộc {CANDIDATE_TEXT_MODES}, nhận được {self.candidate_text!r}")
        if self.dtype not in DTYPES:
            raise ValueError(f"dtype phải thuộc {DTYPES}, nhận được {self.dtype!r}")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model phải là chuỗi không rỗng")
        for name in ("rerank_top_k", "max_candidates", "batch_size", "max_length"):
            _require_positive_int(name, getattr(self, name))
        if self.rerank_top_k > self.max_candidates:
            raise ValueError("rerank_top_k không được lớn hơn max_candidates")
        if self.device is not None and (not isinstance(self.device, str) or not self.device.strip()):
            raise ValueError("device phải là chuỗi không rỗng hoặc null")


def load_reranker_config(path: str | Path = DEFAULT_CONFIG_PATH, **overrides: Any) -> RerankerConfig:
    """Read the ``reranker`` section; non-None ``overrides`` (e.g. from CLI flags) win."""
    import yaml

    config_path = Path(path)
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Không đọc được cấu hình reranker {config_path}: {exc}") from exc
    section = data.get("reranker") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        raise ValueError(f"{config_path} thiếu mục 'reranker'")
    allowed = {field.name for field in fields(RerankerConfig)}
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ValueError(f"Khóa cấu hình reranker không được hỗ trợ: {', '.join(unknown)}")
    values = {**section, **{key: value for key, value in overrides.items() if value is not None}}
    return RerankerConfig(**values)


def candidate_text(hit: Mapping[str, Any], mode: str = "chunk_text") -> str:
    """Content to score: the contract field ``chunk_text``, else the RRF/BM25 ``text`` alias.

    ``breadcrumb_chunk_text`` puts the chunk's breadcrumb (from ``metadata`` or the hit)
    on the line before it; chunks without a breadcrumb are scored on their text alone.
    """
    text = str(hit.get("chunk_text") or hit.get("text") or "")
    if mode == "breadcrumb_chunk_text":
        metadata = hit.get("metadata") if isinstance(hit.get("metadata"), Mapping) else {}
        breadcrumb = metadata.get("breadcrumb") or hit.get("breadcrumb")
        if breadcrumb:
            return f"{breadcrumb}\n{text}"
    return text


def deduplicate_candidates(hits: Sequence[Mapping[str, Any]] | None) -> tuple[list[dict[str, Any]], int]:
    """Keep the first (best-ranked) hit per chunk_id; fill its empty fields from later copies.

    Returns copies, so callers may modify them without touching the input.
    """
    kept: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for hit in hits or []:
        if not isinstance(hit, Mapping):
            raise ValueError("Mỗi candidate phải là object")
        chunk_id = hit.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("Candidate thiếu chunk_id hợp lệ")
        if chunk_id not in kept:
            kept[chunk_id] = copy.deepcopy(dict(hit))
            continue
        duplicates += 1
        row = kept[chunk_id]
        for key, value in hit.items():
            if row.get(key) in (None, "", {}, []) and value not in (None, "", {}, []):
                row[key] = copy.deepcopy(value)
    return list(kept.values()), duplicates


class Scorer(Protocol):
    """Return one relevance score per candidate, in input order."""

    def score(self, query: str, candidates: Sequence[Mapping[str, Any]]) -> list[float]: ...


def _tokens(text: str) -> set[str]:
    # Word-segmented text joins syllables with "_"; split them back for overlap.
    return set(_TOKEN_PATTERN.findall(text.casefold().replace("_", " ")))


class MockScorer:
    """Deterministic, dependency-free stub for mock-first tests and offline CLI runs.

    With ``scores`` it returns the fixed score of each chunk_id (``default`` when
    absent); otherwise the share of distinct query tokens found in the chunk text.
    It is a stub, not a relevance model.
    """

    def __init__(self, scores: Mapping[str, float] | None = None, *, default: float = 0.0,
                 text_mode: str = "chunk_text"):
        self.scores = dict(scores) if scores is not None else None
        self.default = default
        self.text_mode = text_mode

    def score(self, query: str, candidates: Sequence[Mapping[str, Any]]) -> list[float]:
        if self.scores is not None:
            return [float(self.scores.get(hit["chunk_id"], self.default)) for hit in candidates]
        query_tokens = _tokens(query)
        if not query_tokens:
            return [0.0] * len(candidates)
        return [len(query_tokens & _tokens(candidate_text(hit, self.text_mode))) / len(query_tokens)
                for hit in candidates]


class CrossEncoderScorer:
    """Lazy sentence-transformers CrossEncoder scorer (default ``BAAI/bge-reranker-v2-m3``)."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, *, batch_size: int = 16,
                 max_length: int = 512, device: str | None = None, dtype: str = "auto", model: Any = None,
                 text_mode: str = "chunk_text"):
        if dtype not in DTYPES:
            raise ValueError(f"dtype phải thuộc {DTYPES}, nhận được {dtype!r}")
        self.model_name = model_name
        self.text_mode = text_mode
        self.batch_size = _require_positive_int("batch_size", batch_size)
        self.max_length = _require_positive_int("max_length", max_length)
        self.device = device
        self.dtype = dtype
        self._model = model

    def load(self) -> None:
        """Load the model now so its load time is not counted as rerank latency."""
        _ = self.model

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "Cần cài sentence-transformers để dùng backend cross_encoder "
                    "(pip install -r requirements.txt) hoặc chọn backend mock"
                ) from exc
            import torch

            dtype = self.resolve_dtype(self.device, torch.cuda.is_available())
            logger.info("Loading cross-encoder %s (%s)", self.model_name, dtype)
            self._model = CrossEncoder(self.model_name, max_length=self.max_length, device=self.device,
                                       model_kwargs={"torch_dtype": getattr(torch, dtype)})
        return self._model

    def resolve_dtype(self, device: str | None, cuda_available: bool) -> str:
        """``auto`` becomes float16 when the model runs on CUDA (``device`` null picks CUDA if present)."""
        if self.dtype != "auto":
            return self.dtype
        on_cuda = device.startswith("cuda") if device else cuda_available
        return "float16" if on_cuda else "float32"

    def score(self, query: str, candidates: Sequence[Mapping[str, Any]]) -> list[float]:
        pairs = [(query, candidate_text(hit, self.text_mode)) for hit in candidates]
        scores = self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)
        return [float(score) for score in scores]


def _incoming_rank(hit: Mapping[str, Any], position: int) -> int:
    rank = hit.get("rank")
    return rank if isinstance(rank, int) and not isinstance(rank, bool) and rank >= 1 else position


class Reranker:
    """Score at most ``max_candidates`` candidates and return the top-k by reranker score."""

    def __init__(self, scorer: Scorer, *, rerank_top_k: int = 5, max_candidates: int = 50,
                 backend: str = "custom", model: str | None = None):
        self.scorer = scorer
        self.rerank_top_k = _require_positive_int("rerank_top_k", rerank_top_k)
        self.max_candidates = _require_positive_int("max_candidates", max_candidates)
        if self.rerank_top_k > self.max_candidates:
            raise ValueError("rerank_top_k không được lớn hơn max_candidates")
        self.backend = backend
        self.model = model
        self.last_stats: dict[str, Any] = {}

    def describe(self) -> dict[str, Any]:
        """Settings recorded with each run (benchmark rule: model, candidate pool, top_k)."""
        settings = {"backend": self.backend, "model": self.model,
                    "rerank_top_k": self.rerank_top_k, "max_candidates": self.max_candidates,
                    "candidate_text": getattr(self.scorer, "text_mode", "chunk_text")}
        if isinstance(self.scorer, CrossEncoderScorer):
            settings["dtype"] = self.scorer.dtype
        return settings

    def rerank(self, query: str, hits: Sequence[Mapping[str, Any]] | None,
               top_k: int | None = None) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query phải là chuỗi không rỗng")
        top_k = self.rerank_top_k if top_k is None else _require_positive_int("top_k", top_k)
        model_load_ms = 0.0
        load = getattr(self.scorer, "load", None)
        if hits and callable(load):
            load_started = time.perf_counter()
            load()
            model_load_ms = round((time.perf_counter() - load_started) * 1000.0, 3)
        started = time.perf_counter()

        pool, duplicates = deduplicate_candidates(hits)
        input_count = len(hits or [])
        truncated = max(0, len(pool) - self.max_candidates)
        pool = pool[:self.max_candidates]

        scores = self.scorer.score(query, pool) if pool else []
        if len(scores) != len(pool):
            raise ValueError(f"Scorer trả {len(scores)} điểm cho {len(pool)} candidate")
        rows = []
        for position, (hit, raw_score) in enumerate(zip(pool, scores), 1):
            score = float(raw_score)
            if not math.isfinite(score):
                raise ValueError(f"Scorer trả điểm không hợp lệ cho {hit['chunk_id']}: {raw_score!r}")
            hit.setdefault("retrieval_rank", _incoming_rank(hit, position))
            hit.setdefault("retrieval_score", hit.get("score", hit.get("rrf_score")))
            hit["score"] = score
            rows.append(hit)
        rows.sort(key=lambda row: (-row["score"], row["retrieval_rank"], row["chunk_id"]))
        ranked = rows[:top_k]
        for rank, row in enumerate(ranked, 1):
            row["rank"] = rank

        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        self.last_stats = {
            "input_candidates": input_count,
            "duplicates_removed": duplicates,
            "truncated_candidates": truncated,
            "scored_candidates": len(pool),
            "output_candidates": len(ranked),
            "rerank_latency_ms": latency_ms,
            "model_load_ms": model_load_ms,
        }
        logger.info("Reranker[%s] input=%d scored=%d (dup=%d, cut=%d) output=%d latency=%.1fms model_load=%.1fms",
                    self.backend, input_count, len(pool), duplicates, truncated, len(ranked), latency_ms,
                    model_load_ms)
        return ranked


def build_reranker(config: RerankerConfig, *, scorer: Scorer | None = None) -> Reranker | None:
    """Create the configured reranker; ``None`` when ``enabled`` is false."""
    if not config.enabled:
        return None
    if scorer is None:
        if config.backend == "mock":
            scorer = MockScorer(text_mode=config.candidate_text)
        else:
            scorer = CrossEncoderScorer(config.model, batch_size=config.batch_size,
                                        max_length=config.max_length, device=config.device,
                                        dtype=config.dtype, text_mode=config.candidate_text)
    model = config.model if config.backend == "cross_encoder" else None
    return Reranker(scorer, rerank_top_k=config.rerank_top_k, max_candidates=config.max_candidates,
                    backend=config.backend, model=model)


__all__ = [
    "BACKENDS", "CANDIDATE_TEXT_MODES", "CrossEncoderScorer", "DEFAULT_CONFIG_PATH", "DTYPES", "DEFAULT_MODEL_NAME", "MockScorer",
    "Reranker", "RerankerConfig", "Scorer", "build_reranker", "candidate_text",
    "deduplicate_candidates", "load_reranker_config",
]
