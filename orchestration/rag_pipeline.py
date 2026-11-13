"""RAG orchestrator, evidence mapper and Grounding Gate (Sprint 9 plan V3, D5.3 + D5.5).

One question goes through::

    candidates (live Hybrid + Cross-Encoder, or a precomputed reranked artifact)
      -> Top rerank_top_k -> Confidence Threshold Filter -> Parent-Context Resolver
      -> ContextPayload [1]..[n] -> Prompt B -> Qwen Gateway (structured JSON)
      -> evidence_index -> citation mapping -> Grounding Gate -> RAGOutputRecord

Rules kept here, not left to callers:

* no candidate, or a top-1 score below the threshold, means no LLM call and an
  ABSTAIN record;
* the model only returns evidence indices; they are mapped back to the child chunk
  through the payload's ``source_map`` and checked by Dev 1's deterministic validator
  against the exact payload rendered into the prompt;
* only a PASS returns the model answer. FAIL, ABSTAIN and NEEDS_CLARIFICATION return
  fixed policy messages; the model text stays in ``retrieval_trace`` for evaluation;
* ``query_id`` is the same in the candidates, the payload, the gateway call and the record.

Gateway, retrieval and artifact errors propagate; the batch runner records them as
errors instead of turning them into abstentions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from generation.prompt_builder import (
    PROMPT_B_VERSION,
    STANDARD_DISCLAIMER,
    build_controlled_rag_prompt,
    get_prompt_hash,
    map_evidence_indices_to_citations,
)
from grounding.citation_validator import validate_citations
from reranking.confidence import (
    DEFAULT_CONFIDENCE_CONFIG,
    ConfidenceConfig,
    apply_confidence_threshold,
    load_confidence_config,
)
from reranking.context_builder import MAX_EVIDENCE_ITEMS, build_context_payload
from reranking.parent_context import ParentContextResolver, load_parent_context_config
from retrieval.temporal import normalize_as_of_date
from schemas.models import (
    ContextPayload,
    GroundingResult,
    LatencyBreakdown,
    LLMResponse,
    RAGOutputRecord,
    TokenUsage,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RETRIEVAL_CONFIG = ROOT / "retrieval" / "config.yaml"
DEFAULT_RERANK_CONFIG = ROOT / "reranking" / "config.yaml"
RUN_MODE = "B_controlled_rag"
NOT_GENERATED = "not_generated"

ABSTAIN_MESSAGE = ("Không tìm thấy đủ căn cứ trong cơ sở dữ liệu pháp luật Hôn nhân và gia đình hiện có "
                   "để trả lời câu hỏi này tại thời điểm {as_of_date}.")
FAIL_MESSAGE = ("Hệ thống không xác minh được căn cứ trích dẫn cho câu trả lời, nên không đưa ra "
                "kết luận pháp lý cho câu hỏi này.")
CLARIFY_MESSAGE = ("Câu hỏi cần thêm thông tin để xác định quy định áp dụng. Vui lòng bổ sung "
                   "tình huống cụ thể (thời điểm, quan hệ giữa các bên, sự kiện pháp lý).")
INLINE_MARKER = re.compile(r"\[(\d{1,2})\]")
# Chữ Hán, kana Nhật, Hangul và dấu câu CJK (《》、。). Tiếng Việt không dùng ký tự nào trong
# các dải này; Qwen trượt sang tiếng Trung khi bị phạt lặp token (Run B 10/11: HN_025, HN_062).
CJK_CHARS = re.compile("[\u3000-\u303f\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uac00-\ud7af"
                       "\U00020000-\U0002fa1f]")


def count_cjk_chars(text: str) -> int:
    return len(CJK_CHARS.findall(text or ""))


class CandidateSource(Protocol):
    """Gives the reranked envelope for one question (results sorted by rank)."""

    name: str

    def fetch(self, *, query_id: str, query: str, as_of_date: str) -> Mapping[str, Any]: ...


class Generator(Protocol):
    config: Any

    def generate(self, prompt: str, query_id: str, run_mode: str, prompt_version: str,
                 structured_output: bool = False, schema: dict[str, Any] | None = None) -> LLMResponse: ...


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RunVersions:
    corpus_version: str
    retrieval_config_version: str
    threshold_config_version: str


def _canonical_hash(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_run_versions(*, corpus_path: str | Path, retrieval_config: str | Path = DEFAULT_RETRIEVAL_CONFIG,
                         rerank_config: str | Path = DEFAULT_RERANK_CONFIG,
                         confidence: ConfidenceConfig | None = None) -> RunVersions:
    """corpus = SHA-256 of the chunk file (LF); retrieval config = hash of the retrieval and
    reranking YAML; the threshold has its own ``threshold_config_version``."""
    import yaml

    from embedding.vector_store import chunk_file_sha256

    retrieval = yaml.safe_load(Path(retrieval_config).read_text(encoding="utf-8")) or {}
    rerank = yaml.safe_load(Path(rerank_config).read_text(encoding="utf-8")) or {}
    if confidence is None:
        confidence = load_confidence_config()
    return RunVersions(
        corpus_version=f"sha256:{chunk_file_sha256(corpus_path)}",
        retrieval_config_version=f"sha256:{_canonical_hash({'retrieval': retrieval, 'reranking': rerank})[:16]}",
        threshold_config_version=confidence.threshold_config_version,
    )


# ---------------------------------------------------------------------------
# Candidate sources
# ---------------------------------------------------------------------------
def _envelope_facts(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Read date, reranker settings and corpus hash from a G3 envelope or a D4.4 record."""
    config = envelope.get("config") or {}
    source_config = envelope.get("source_run_config") or {}
    reranker = envelope.get("reranker_config") or config.get("reranker") or source_config.get("reranker")
    retriever = config.get("retriever") or source_config.get("retriever") or {}
    parent = config.get("parent_context") if "parent_context" in config else source_config.get("parent_context")
    return {
        "as_of_date": envelope.get("as_of_date") or config.get("as_of_date"),
        "reranker": reranker if isinstance(reranker, Mapping) else None,
        "corpus_sha256": retriever.get("corpus_sha256") if isinstance(retriever, Mapping) else None,
        "retriever": retriever if isinstance(retriever, Mapping) else {},
        "parent_context": parent,
    }


class PrecomputedRerankedSource:
    """Reranked envelopes saved by an earlier run (G3 ``retrieval/results/dev_hybrid_reranker.json``
    or Dev 4's D4.4 JSONL). Refuses an artifact made on another corpus, another candidate text,
    a mock scorer, other retrieval/reranker settings (``expected_settings``), another question
    text or another date, so the record's config versions describe the run that made it."""

    name = "precomputed"
    # Retrieval and rerank ran in an earlier process: their time is unknown, so
    # latency_breakdown.retrieval_ms stays null instead of the near-zero lookup time.
    measures_retrieval = False

    def __init__(self, envelopes: Sequence[Mapping[str, Any]], *, expected_corpus_sha256: str,
                 expected_candidate_text: str,
                 expected_settings: Mapping[str, Mapping[str, Any]] | None = None,
                 source_path: str = "in-memory"):
        if not envelopes:
            raise ValueError("Artifact precomputed không có câu hỏi nào")
        self.source_path = source_path
        self.envelopes: dict[str, Mapping[str, Any]] = {}
        for envelope in envelopes:
            query_id = envelope.get("query_id") if isinstance(envelope, Mapping) else None
            if not isinstance(query_id, str) or not query_id or not isinstance(envelope.get("results"), list):
                raise ValueError("Mỗi bản ghi precomputed cần query_id và results")
            if query_id in self.envelopes:
                raise ValueError(f"query_id bị trùng trong artifact precomputed: {query_id}")
            facts = _envelope_facts(envelope)
            reranker = facts["reranker"]
            if reranker is None:
                raise ValueError(f"{query_id}: artifact chưa qua reranker")
            if reranker.get("backend") != "cross_encoder":
                raise ValueError(f"{query_id}: reranker backend {reranker.get('backend')!r}, cần cross_encoder")
            if reranker.get("candidate_text") != expected_candidate_text:
                raise ValueError(f"{query_id}: candidate_text {reranker.get('candidate_text')!r} khác cấu hình "
                                 f"{expected_candidate_text!r}")
            if facts["corpus_sha256"] != expected_corpus_sha256:
                raise ValueError(f"{query_id}: artifact làm trên corpus {facts['corpus_sha256']!r}, "
                                 f"corpus hiện tại {expected_corpus_sha256!r}; hãy chạy lại retrieval/rerank")
            sections = {"retriever": facts["retriever"], "reranker": reranker}
            for section, expected in (expected_settings or {}).items():
                for key, value in expected.items():
                    saved = sections[section].get(key)
                    if saved != value:
                        raise ValueError(f"{query_id}: artifact có {section}.{key}={saved!r}, cấu hình hiện tại "
                                         f"{value!r}; hãy chạy lại retrieval/rerank")
            self.envelopes[query_id] = envelope

    @classmethod
    def from_file(cls, path: str | Path, **kwargs: Any) -> "PrecomputedRerankedSource":
        source = Path(path)
        text = source.read_text(encoding="utf-8-sig")
        if source.suffix == ".jsonl":
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            loaded = json.loads(text)
            data = loaded if isinstance(loaded, list) else [loaded]
        return cls(data, source_path=str(source), **kwargs)

    def fetch(self, *, query_id: str, query: str, as_of_date: str) -> Mapping[str, Any]:
        envelope = self.envelopes.get(query_id)
        if envelope is None:
            raise ValueError(f"Artifact precomputed không có query_id {query_id}")
        if str(envelope.get("query", "")).strip() != query.strip():
            raise ValueError(f"Câu hỏi của {query_id} khác câu hỏi trong artifact precomputed")
        saved = _envelope_facts(envelope)["as_of_date"]
        if saved != as_of_date:
            raise ValueError(f"{query_id}: artifact dùng as_of_date {saved!r}, lần chạy này {as_of_date!r}")
        return envelope


class LivePipelineSource:
    """Live Hybrid + Cross-Encoder + Parent-Context through ``reranking.pipeline.RetrievalPipeline``."""

    name = "live"
    measures_retrieval = True  # fetch() = Hybrid retrieval + Cross-Encoder rerank + parent context

    def __init__(self, pipeline: Any):
        if getattr(pipeline, "reranker", None) is None:
            raise ValueError("Pipeline live phải có reranker (Top-50 -> Top-5)")
        self.pipeline = pipeline

    def fetch(self, *, query_id: str, query: str, as_of_date: str) -> Mapping[str, Any]:
        return self.pipeline.run(query, query_id=query_id, as_of_date=as_of_date)


# ---------------------------------------------------------------------------
# Grounding Gate (D5.5)
# ---------------------------------------------------------------------------
def _gate_result(status: str, reason: str, invalid: Sequence[int] = ()) -> GroundingResult:
    return GroundingResult(grounding_status=status, is_grounded=False,
                           invalid_indices=sorted({i for i in invalid if type(i) is int}), reason=reason)


def apply_grounding_gate(payload: ContextPayload, llm: LLMResponse) -> GroundingResult:
    """Deterministic Gate. PASS only when the output parsed cleanly, was not truncated,
    did not abstain, has no CJK characters (``ANSWER_NOT_VIETNAMESE``), and every cited
    index (structured and inline ``[n]``) maps to the payload rendered into the prompt.

    No check on words such as "nước ngoài": a correct answer may say "công dân Việt Nam
    với người nước ngoài" (HN_062)."""
    if llm.query_id != payload.query_id:
        return _gate_result("FAIL", "QUERY_ID_MISMATCH")
    if llm.parse_status != "ok":
        return _gate_result("FAIL", f"LLM_OUTPUT_{llm.parse_status.upper()}")
    if llm.truncated or llm.done_reason == "length":
        return _gate_result("FAIL", "LLM_OUTPUT_TRUNCATED")
    if llm.context_truncated:
        return _gate_result("FAIL", "PROMPT_CONTEXT_TRUNCATED")
    if llm.rejected_evidence_values:
        return _gate_result("FAIL", "NON_INTEGER_EVIDENCE_INDEX")
    if llm.abstained:
        return _gate_result("ABSTAIN", "MODEL_ABSTAINED")
    if llm.needs_clarification:
        return _gate_result("NEEDS_CLARIFICATION", "MODEL_NEEDS_CLARIFICATION")
    if not llm.answer.strip():
        return _gate_result("FAIL", "EMPTY_ANSWER")
    if count_cjk_chars(llm.answer):
        return _gate_result("FAIL", "ANSWER_NOT_VIETNAMESE")
    citations, invalid = map_evidence_indices_to_citations(llm.evidence_indices, payload)
    result = validate_citations(payload, citations, evidence_indices=llm.evidence_indices,
                                invalid_indices=invalid)
    if result.grounding_status != "PASS":
        return result
    if any(item.chunk_id in llm.answer for item in payload.evidence_items):
        return _gate_result("FAIL", "ANSWER_CONTAINS_CHUNK_ID")
    inline = {int(n) for n in INLINE_MARKER.findall(llm.answer)}
    outside = sorted(inline - set(payload.source_map))
    if outside:
        return _gate_result("FAIL", "ANSWER_MARKER_OUTSIDE_CONTEXT", outside)
    uncited = sorted(inline - set(llm.evidence_indices))
    if uncited:
        return _gate_result("FAIL", "ANSWER_MARKER_NOT_IN_EVIDENCE_INDICES", uncited)
    return result


def with_disclaimer(answer: str) -> str:
    answer = answer.strip()
    return answer if STANDARD_DISCLAIMER in answer else f"{answer}\n\n{STANDARD_DISCLAIMER}"


def abstention_fields(grounding: GroundingResult, *, llm_called: bool) -> dict[str, Any]:
    """Top-level abstention fields of a record (P45-4), filled on every path.

    ``abstention_reason`` is a fixed code the evaluator can count; the model's own wording
    stays in ``retrieval_trace.llm.abstention_reason``. A Gate FAIL counts as an abstention
    because the user only gets the no-conclusion message."""
    status = grounding.grounding_status
    if status == "PASS":
        return {"abstained": False, "abstention_reason": None, "abstention_source": None,
                "needs_clarification": False}
    if status == "NEEDS_CLARIFICATION":
        return {"abstained": False, "abstention_reason": None, "abstention_source": "model",
                "needs_clarification": True}
    if status == "ABSTAIN":
        source = "model" if llm_called else "confidence_filter"
    else:
        source = "grounding_gate"
    return {"abstained": True, "abstention_reason": grounding.reason or f"{status}_WITHOUT_REASON",
            "abstention_source": source, "needs_clarification": False}


def _ms(value: Any) -> float | None:
    return None if value is None else round(float(value), 2)


def latency_breakdown(llm: LLMResponse | None, *, retrieval_ms: float | None) -> LatencyBreakdown:
    """Per-step times (P45-6). The Ollama durations come from the gateway (P45-3) and stay
    null when Ollama did not return them; nothing is set to 0."""
    if llm is None:
        return LatencyBreakdown(retrieval_ms=retrieval_ms)
    return LatencyBreakdown(
        retrieval_ms=retrieval_ms,
        llm_total_ms=_ms(llm.latency_ms),
        ttft_model_ms=_ms(llm.ttft_model_ms),
        load_ms=_ms(llm.load_duration_ms),
        prompt_eval_ms=_ms(llm.prompt_eval_duration_ms),
        eval_ms=_ms(llm.eval_duration_ms),
    )


def policy_message(status: str, as_of_date: str) -> str:
    if status == "ABSTAIN":
        text = ABSTAIN_MESSAGE.format(as_of_date=as_of_date)
    elif status == "NEEDS_CLARIFICATION":
        text = CLARIFY_MESSAGE
    else:
        text = FAIL_MESSAGE
    return with_disclaimer(text)


# ---------------------------------------------------------------------------
# Orchestrator (D5.3)
# ---------------------------------------------------------------------------
@dataclass
class RAGRunResult:
    record: RAGOutputRecord
    payload: ContextPayload | None = None
    llm_response: LLMResponse | None = None
    grounding: GroundingResult | None = None
    prompt: str | None = None
    trace: dict[str, Any] = field(default_factory=dict)


class RAGPipeline:
    def __init__(self, source: CandidateSource, generator: Generator, *, versions: RunVersions,
                 confidence: ConfidenceConfig, rerank_top_k: int, max_context_chars: int,
                 parent_resolver: ParentContextResolver | None = None):
        if not 1 <= rerank_top_k <= MAX_EVIDENCE_ITEMS:
            raise ValueError(f"rerank_top_k phải trong [1, {MAX_EVIDENCE_ITEMS}]")
        self.source = source
        self.generator = generator
        self.versions = versions
        self.confidence = confidence
        self.rerank_top_k = rerank_top_k
        self.max_context_chars = max_context_chars
        self.parent_resolver = parent_resolver
        if versions.threshold_config_version != confidence.threshold_config_version:
            raise ValueError("threshold_config_version của versions khác cấu hình confidence")

    def _model_meta(self) -> dict[str, Any]:
        config = self.generator.config
        return {"model": config.model, "num_ctx": config.num_ctx, "num_predict": config.num_predict}

    def _rows(self, envelope: Mapping[str, Any], query_id: str) -> list[dict[str, Any]]:
        if envelope.get("query_id") != query_id:
            raise ValueError(f"Candidate source trả query_id {envelope.get('query_id')!r}, cần {query_id!r}")
        rows = [dict(row) for row in envelope.get("results") or []]
        ranks = [row.get("rank") for row in rows]
        if any(type(r) is not int for r in ranks) or any(b <= a for a, b in zip(ranks, ranks[1:])):
            raise ValueError(f"{query_id}: results phải có rank nguyên tăng dần")
        return rows[:self.rerank_top_k]

    def run(self, *, query_id: str, query: str, as_of_date: str, as_of_date_source: str) -> RAGRunResult:
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError("query_id không được rỗng")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query không được rỗng")
        query_id, query = query_id.strip(), query.strip()
        as_of_date = normalize_as_of_date(as_of_date)
        started = time.perf_counter()

        envelope = self.source.fetch(query_id=query_id, query=query, as_of_date=as_of_date)
        retrieval_ms = (round((time.perf_counter() - started) * 1000.0, 2)
                        if getattr(self.source, "measures_retrieval", False) else None)
        rows = self._rows(envelope, query_id)
        decision = apply_confidence_threshold(rows, self.confidence)
        trace: dict[str, Any] = {
            "candidate_source": self.source.name,
            "retriever": envelope.get("retriever"),
            "as_of_date_source": as_of_date_source,
            "rerank_top_k": self.rerank_top_k,
            "candidates": [{"rank": r.get("rank"), "chunk_id": r.get("chunk_id"),
                            "reranker_score": r.get("reranker_score")} for r in rows],
            "confidence": {**decision.describe(), **self.confidence.describe()},
        }
        if decision.status != "ok":
            reason = "EMPTY_RETRIEVAL" if decision.status == "empty" else "LOW_CONFIDENCE"
            grounding = _gate_result("ABSTAIN", reason)
            return self._finish(query_id, query, as_of_date, as_of_date_source, started, trace,
                                grounding=grounding, payload=None, llm=None, prompt=None,
                                retrieval_ms=retrieval_ms)

        kept = decision.kept
        if self.parent_resolver is not None and any("parent_text" not in row for row in kept):
            kept = self.parent_resolver.resolve(kept)
            trace["parent_context"] = dict(self.parent_resolver.last_stats)
        payload, context_trace = build_context_payload(
            kept, query_id=query_id, query=query, as_of_date=as_of_date, as_of_date_source=as_of_date_source,
            max_context_chars=self.max_context_chars, max_items=self.rerank_top_k)
        trace["context"] = context_trace

        prompt = build_controlled_rag_prompt(payload)
        trace["prompt_sha256"] = get_prompt_hash(prompt)
        llm = self.generator.generate(prompt, query_id, RUN_MODE, PROMPT_B_VERSION, structured_output=True)
        grounding = apply_grounding_gate(payload, llm)
        return self._finish(query_id, query, as_of_date, as_of_date_source, started, trace,
                            grounding=grounding, payload=payload, llm=llm, prompt=prompt,
                            retrieval_ms=retrieval_ms)

    def _finish(self, query_id: str, query: str, as_of_date: str, as_of_date_source: str, started: float,
                trace: dict[str, Any], *, grounding: GroundingResult, payload: ContextPayload | None,
                llm: LLMResponse | None, prompt: str | None, retrieval_ms: float | None) -> RAGRunResult:
        status = grounding.grounding_status
        trace["gate"] = {"status": status, "reason": grounding.reason, "invalid_indices": grounding.invalid_indices}
        if llm is not None:
            trace["llm"] = {
                "answer_before_gate": llm.answer,
                "cjk_chars_before_gate": count_cjk_chars(llm.answer),
                "evidence_indices": llm.evidence_indices,
                "rejected_evidence_values": llm.rejected_evidence_values,
                "abstained": llm.abstained,
                "abstention_reason": llm.abstention_reason,
                "needs_clarification": llm.needs_clarification,
                "parse_status": llm.parse_status,
                "context_truncated": llm.context_truncated,
                "temperature": llm.temperature,
                "repeat_penalty": llm.repeat_penalty,
                "ollama_version": llm.ollama_version,
                "model_digest": llm.model_digest,
                "latency_ms": llm.latency_ms,
            }
        answer = with_disclaimer(llm.answer) if status == "PASS" and llm is not None else policy_message(status, as_of_date)
        meta = self._model_meta()
        record = RAGOutputRecord(
            query_id=query_id,
            query=query,
            as_of_date=as_of_date,
            as_of_date_source=as_of_date_source,
            answer=answer,
            evidence_indices=list(llm.evidence_indices) if llm is not None else [],
            citations=list(grounding.valid_citations) if status == "PASS" else [],
            grounding_status=status,
            **abstention_fields(grounding, llm_called=llm is not None),
            retrieval_trace=trace,
            model=llm.model if llm is not None else meta["model"],
            prompt_version=PROMPT_B_VERSION,
            num_ctx=llm.num_ctx if llm is not None else meta["num_ctx"],
            num_predict=llm.num_predict if llm is not None else meta["num_predict"],
            done_reason=llm.done_reason if llm is not None else NOT_GENERATED,
            truncated=llm.truncated if llm is not None else False,
            corpus_version=self.versions.corpus_version,
            retrieval_config_version=self.versions.retrieval_config_version,
            threshold_config_version=self.versions.threshold_config_version,
            latency_ms=round((time.perf_counter() - started) * 1000.0, 2),
            llm_calls=1 if llm is not None else 0,
            latency_breakdown=latency_breakdown(llm, retrieval_ms=retrieval_ms),
            token_usage=llm.token_usage if llm is not None else TokenUsage(),
            fallback_status=llm.fallback_status if llm is not None else "none",
        )
        return RAGRunResult(record=record, payload=payload, llm_response=llm, grounding=grounding,
                            prompt=prompt, trace=trace)


# ---------------------------------------------------------------------------
# Factory and the shared ``run_rag`` adapter for scripts/run_rag_batch.py (Dev 4)
# ---------------------------------------------------------------------------
def build_pipeline(*, precomputed: str | Path | None = None, generator: Generator | None = None,
                   rerank_config: str | Path = DEFAULT_RERANK_CONFIG,
                   retrieval_config: str | Path = DEFAULT_RETRIEVAL_CONFIG,
                   confidence_config: str | Path = DEFAULT_CONFIDENCE_CONFIG,
                   elasticsearch_url: str | None = None, qdrant_path: str | None = None) -> RAGPipeline:
    """Precomputed artifact when given (official Run B), else live Hybrid + Cross-Encoder."""
    from reranking.pipeline import RetrievalPipeline, build_hybrid_retriever, load_retrieval_settings
    from reranking.reranker import build_reranker, load_reranker_config

    settings = load_retrieval_settings(retrieval_config)
    reranker_config = load_reranker_config(rerank_config)
    parent_config = load_parent_context_config(rerank_config)
    confidence = load_confidence_config(confidence_config)
    versions = compute_run_versions(corpus_path=settings["corpus_path"], retrieval_config=retrieval_config,
                                    rerank_config=rerank_config, confidence=confidence)
    resolver = ParentContextResolver.from_config(parent_config) if parent_config.enabled else None
    if precomputed is not None:
        source: CandidateSource = PrecomputedRerankedSource.from_file(
            precomputed, expected_corpus_sha256=versions.corpus_version.removeprefix("sha256:"),
            expected_candidate_text=reranker_config.candidate_text,
            expected_settings={
                "retriever": {"retrieval_top_k": settings["retrieval_top_k"], "rrf_k": settings["rrf_k"],
                              "dense_model": settings["dense_model"]},
                "reranker": {"model": reranker_config.model, "max_candidates": reranker_config.max_candidates},
            })
    else:
        retriever = build_hybrid_retriever(settings, elasticsearch_url=elasticsearch_url, qdrant_path=qdrant_path)
        live = RetrievalPipeline(retriever, build_reranker(reranker_config),
                                 retrieval_top_k=settings["retrieval_top_k"], parent_resolver=resolver)
        source = LivePipelineSource(live)
    if generator is None:
        from model_gateway.llm_gateway import QwenGateway

        generator = QwenGateway()
    return RAGPipeline(source, generator, versions=versions, confidence=confidence,
                       rerank_top_k=reranker_config.rerank_top_k,
                       max_context_chars=parent_config.max_context_chars, parent_resolver=resolver)


_DEFAULT_PIPELINE: RAGPipeline | None = None


def run_rag(query: Mapping[str, Any]) -> dict[str, Any]:
    """Batch adapter: ``{"query_id", "query", "as_of_date"}`` from the benchmark -> record dict.

    Built once per process from ``RAG_PRECOMPUTED`` (artifact path) or, when unset, live
    retrieval from ``ELASTICSEARCH_URL``/``QDRANT_PATH``. The date always comes from the
    benchmark row (``as_of_date_source="benchmark"``).
    """
    global _DEFAULT_PIPELINE
    if _DEFAULT_PIPELINE is None:
        _DEFAULT_PIPELINE = build_pipeline(precomputed=os.getenv("RAG_PRECOMPUTED") or None,
                                           elasticsearch_url=os.getenv("ELASTICSEARCH_URL"),
                                           qdrant_path=os.getenv("QDRANT_PATH"))
    result = _DEFAULT_PIPELINE.run(query_id=query["query_id"], query=query["query"],
                                   as_of_date=query["as_of_date"], as_of_date_source="benchmark")
    return result.record.model_dump(mode="json")


__all__ = [
    "LivePipelineSource", "PrecomputedRerankedSource", "RAGPipeline", "RAGRunResult", "RunVersions",
    "abstention_fields", "apply_grounding_gate", "build_pipeline", "compute_run_versions", "count_cjk_chars",
    "latency_breakdown", "policy_message", "run_rag", "with_disclaimer",
]
