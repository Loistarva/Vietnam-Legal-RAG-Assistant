"""Deterministic, rule-based request routing before legal retrieval or generation.

The router is deliberately independent of retrieval, LLM, and web frameworks.
No fast-path rules are enabled by default: a rule must be explicitly approved
and carry non-empty handler and citation references before it can match. The
downstream orchestrator remains responsible for validating those references.
"""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Sequence


CLASSIFIER_VERSION = "rule_router_v1"
_LOGGER = logging.getLogger(__name__)


class Route(str, Enum):
    """Primary destinations plus conservative legal-scope outcomes."""

    LEGAL_HNGD = "LEGAL_HNGD"
    LEGAL_OUT_OF_SCOPE = "LEGAL_OUT_OF_SCOPE"
    NON_LEGAL = "NON_LEGAL"
    MIXED_LEGAL_SCOPE = "MIXED_LEGAL_SCOPE"
    LEGAL_SCOPE_UNCERTAIN = "LEGAL_SCOPE_UNCERTAIN"


class Action(str, Enum):
    LEGAL_RETRIEVAL = "LEGAL_RETRIEVAL"
    POLICY_ABSTENTION = "POLICY_ABSTENTION"
    GENERAL_CHAT = "GENERAL_CHAT"
    FAST_PATH = "FAST_PATH"


class RouteReason(str, Enum):
    FAST_PATH_RULE_MATCH = "FAST_PATH_RULE_MATCH"
    HNGD_DOMAIN_MATCH = "HNGD_DOMAIN_MATCH"
    LEGAL_OUT_OF_SCOPE_MATCH = "LEGAL_OUT_OF_SCOPE_MATCH"
    LEGAL_SCOPE_UNCERTAIN = "LEGAL_SCOPE_UNCERTAIN"
    MIXED_LEGAL_SCOPE = "MIXED_LEGAL_SCOPE"
    NON_LEGAL_NO_LEGAL_INTENT = "NON_LEGAL_NO_LEGAL_INTENT"
    INVALID_EMPTY_QUERY = "INVALID_EMPTY_QUERY"
    INVALID_QUERY_TYPE = "INVALID_QUERY_TYPE"
    INVALID_AS_OF_DATE = "INVALID_AS_OF_DATE"


class RouterInputError(ValueError):
    """Input validation failure with a stable reason code for callers."""

    def __init__(self, message: str, *, reason_code: RouteReason):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class RouteDecision:
    """Structured routing result; it contains no answer text or citations."""

    query_id: str | None
    route: Route
    action: Action
    route_reason: RouteReason
    matched_rule_id: str | None = None
    fast_path: bool = False
    classifier_version: str = CLASSIFIER_VERSION
    as_of_date: str | date | datetime | None = None

    def to_dict(self) -> dict[str, str | bool | None]:
        as_of_date = self.as_of_date
        if isinstance(as_of_date, (date, datetime)):
            as_of_date = as_of_date.isoformat()
        return {
            "query_id": self.query_id,
            "route": self.route.value,
            "action": self.action.value,
            "route_reason": self.route_reason.value,
            "matched_rule_id": self.matched_rule_id,
            "fast_path": self.fast_path,
            "classifier_version": self.classifier_version,
            "as_of_date": as_of_date,
        }


@dataclass(frozen=True)
class FastPathRule:
    """Approved exact-query whitelist rule with an effective period.

    ``patterns`` are complete normalized query templates, not substring
    keywords. ``effective_to`` is exclusive, matching retrieval's temporal
    contract. A date-bounded rule does not match when no as_of_date is supplied.
    """

    rule_id: str
    patterns: tuple[str, ...]
    response_key: str | None = None
    citation_refs: tuple[str, ...] = ()
    effective_from: str | None = None
    effective_to: str | None = None
    approved: bool = False

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("FastPathRule.rule_id không được rỗng.")
        if not self.patterns:
            raise ValueError(f"FastPathRule {self.rule_id} cần ít nhất một pattern.")
        for pattern in self.patterns:
            if not isinstance(pattern, str) or not normalize_query(pattern):
                raise ValueError(f"FastPathRule {self.rule_id} có pattern không hợp lệ.")
        start = _parse_rule_date(self.effective_from, "effective_from")
        end = _parse_rule_date(self.effective_to, "effective_to")
        if start and end and start >= end:
            raise ValueError("effective_from phải sớm hơn effective_to (exclusive).")

    def matches(self, normalized_query: str, as_of_date: str | date | datetime | None) -> bool:
        if not self.approved or not self.response_key or not self.citation_refs:
            return False
        if normalized_query not in {normalize_query(pattern) for pattern in self.patterns}:
            return False

        start = _parse_rule_date(self.effective_from, "effective_from")
        end = _parse_rule_date(self.effective_to, "effective_to")
        if start is None and end is None:
            return True
        as_of = _parse_as_of_date(as_of_date)
        if as_of is None:
            return False
        return (start is None or start <= as_of) and (end is None or as_of < end)


def normalize_query(query: str) -> str:
    """NFC normalize, casefold, and collapse whitespace without stripping accents."""

    normalized = unicodedata.normalize("NFC", query)
    return " ".join(normalized.split()).casefold()


def _parse_as_of_date(value: str | date | datetime | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise RouterInputError(
            "as_of_date phải là YYYY-MM-DD, date, hoặc None.",
            reason_code=RouteReason.INVALID_AS_OF_DATE,
        )
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise RouterInputError(
            f"as_of_date không hợp lệ: {value!r}; yêu cầu YYYY-MM-DD.",
            reason_code=RouteReason.INVALID_AS_OF_DATE,
        ) from exc
    if parsed.isoformat() != value.strip():
        raise RouterInputError(
            f"as_of_date phải có định dạng YYYY-MM-DD: {value!r}.",
            reason_code=RouteReason.INVALID_AS_OF_DATE,
        )
    return parsed


def _parse_rule_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} phải có định dạng YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} không hợp lệ: {value!r}.") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} phải có định dạng YYYY-MM-DD.")
    return parsed


# Strong legal signals; ordinary family terms and generic words such as "đất"
# are intentionally absent. Topic-specific question patterns are checked too.
_LEGAL_SIGNALS = (
    "pháp luật",
    "theo luật",
    "theo quy định",
    "quy định pháp luật",
    "nghị định",
    "thông tư",
    "điều luật",
    "khoản luật",
    "trái pháp luật",
    "vi phạm pháp luật",
    "trách nhiệm pháp lý",
    "tư vấn pháp luật",
    "tư vấn pháp lý",
    "xử phạt",
    "bị phạt",
    "hình phạt",
    "truy cứu trách nhiệm",
    "quyền và nghĩa vụ",
    "ai có quyền",
    "quyền pháp lý",
    "thủ tục pháp lý",
    "hợp pháp",
    "bị cấm",
    "đúng luật",
    "sai quy định",
    "luật thuế",
)

_HNGD_TERMS = (
    "hôn nhân và gia đình",
    "luật hôn nhân",
    "hngđ",
    "hngd",
    "kết hôn",
    "đăng ký kết hôn",
    "ly hôn",
    "hủy kết hôn",
    "hủy việc kết hôn",
    "cấp dưỡng",
    "quyền nuôi con",
    "nuôi con sau ly hôn",
    "chế độ tài sản",
    "tài sản chung của vợ chồng",
    "tài sản riêng của vợ chồng",
    "quan hệ vợ chồng",
    "quyền và nghĩa vụ của vợ chồng",
    "xác định cha, mẹ, con",
    "xác định cha mẹ con",
    "mang thai hộ",
    "kết hôn với người nước ngoài",
)

_OUT_OF_SCOPE_TERMS = (
    "luật thuế",
    "thuế thu nhập cá nhân",
    "thuế doanh nghiệp",
    "kê khai thuế",
    "nghĩa vụ thuế",
    "trốn thuế",
    "cấp sổ đỏ",
    "sổ đỏ",
    "quyền sử dụng đất",
    "chuyển nhượng đất",
    "tội trộm cắp",
    "tội phạm",
    "hình sự",
    "trách nhiệm hình sự",
    "hợp đồng lao động",
    "sa thải",
    "bảo hiểm xã hội",
    "vi phạm giao thông",
    "giấy phép lái xe",
    "xử phạt giao thông",
    "thành lập công ty",
    "đăng ký kinh doanh",
    "phá sản doanh nghiệp",
    "hợp đồng mua bán nhà đất",
    "phạt vì đỗ xe",
    "đỗ xe sai quy định",
)

_LEGAL_QUESTION_MARKERS = (
    "quy định",
    "là gì",
    "thế nào",
    "ra sao",
    "bao lâu",
    "bao nhiêu",
    "có được",
    "được phép",
    "ai có quyền",
    "quyền gì",
    "nghĩa vụ gì",
    "nghĩa vụ",
    "điều kiện",
    "thủ tục",
    "bị xử lý",
    "xử lý thế nào",
    "mức phạt",
    "tìm hiểu",
    "muốn hỏi",
    "hỏi về",
    "giải thích",
    "tư vấn",
    "cần làm gì",
    "có bắt buộc",
    "phải làm gì",
    "chia tài sản",
    "phân chia tài sản",
    "cần giấy tờ gì",
    "cần những giấy tờ gì",
    "có đúng luật không",
    "quy định gì",
)

_EDUCATION_STATEMENT = re.compile(
    r"\b(?:tôi|em|mình)\s+(?:đang\s+)?(?:học|nghiên cứu)\s+(?:môn\s+)?luật\b"
)
_EXPLICIT_QUESTION_OR_REQUEST = re.compile(
    r"\?|\b(?:là gì|thế nào|ra sao|giải thích|cho biết|tư vấn|tìm hiểu|"
    r"có được|điều kiện|quyền gì|nghĩa vụ gì|bao lâu|bao nhiêu)\b"
)
_LEGAL_CITATION = re.compile(r"\b(?:điều|khoản)\s+\d+\b")


class RuleRouter:
    """Normalize, run approved fast-path rules first, then classify legal scope."""

    def __init__(
        self,
        fast_path_rules: Sequence[FastPathRule] = (),
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.fast_path_rules = tuple(fast_path_rules)
        rule_ids = [rule.rule_id for rule in self.fast_path_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("FastPathRule.rule_id phải duy nhất.")
        normalized_patterns: dict[str, str] = {}
        for rule in self.fast_path_rules:
            for pattern in rule.patterns:
                normalized = normalize_query(pattern)
                previous_rule = normalized_patterns.get(normalized)
                if previous_rule is not None:
                    raise ValueError(
                        "FastPathRule có exact pattern bị trùng sau chuẩn hóa: "
                        f"{previous_rule!r} và {rule.rule_id!r}."
                    )
                normalized_patterns[normalized] = rule.rule_id
        self.logger = logger or _LOGGER

    def route(
        self,
        query: str,
        *,
        query_id: str | None = None,
        as_of_date: str | date | datetime | None = None,
        source: str | None = None,
    ) -> RouteDecision:
        """Return a decision without invoking retrieval, a responder, or an LLM."""

        started = time.perf_counter()
        if not isinstance(query, str):
            raise RouterInputError(
                "query phải là string.", reason_code=RouteReason.INVALID_QUERY_TYPE
            )
        if not query.strip():
            raise RouterInputError(
                "query không được rỗng hoặc chỉ chứa khoảng trắng.",
                reason_code=RouteReason.INVALID_EMPTY_QUERY,
            )
        if query_id is not None and not isinstance(query_id, str):
            raise RouterInputError(
                "query_id phải là string hoặc None.",
                reason_code=RouteReason.INVALID_QUERY_TYPE,
            )
        if source is not None and not isinstance(source, str):
            raise RouterInputError(
                "source phải là string hoặc None.",
                reason_code=RouteReason.INVALID_QUERY_TYPE,
            )
        _parse_as_of_date(as_of_date)

        normalized = normalize_query(query)
        decision = self._match_fast_path(normalized, query_id, as_of_date)
        if decision is None:
            decision = self._classify_normalized_query(
                normalized, query_id=query_id, as_of_date=as_of_date
            )

        duration_ms = (time.perf_counter() - started) * 1000
        event = {
            "event": "route_decision",
            **decision.to_dict(),
            "source": source,
            "duration_ms": round(duration_ms, 3),
        }
        # Do not log raw or normalized user query text.
        self.logger.info("%s", json.dumps(event, ensure_ascii=False, separators=(",", ":")))
        return decision

    def _match_fast_path(
        self,
        normalized_query: str,
        query_id: str | None,
        as_of_date: str | date | datetime | None,
    ) -> RouteDecision | None:
        for rule in self.fast_path_rules:
            if rule.matches(normalized_query, as_of_date):
                return RouteDecision(
                    query_id=query_id,
                    route=Route.LEGAL_HNGD,
                    action=Action.FAST_PATH,
                    route_reason=RouteReason.FAST_PATH_RULE_MATCH,
                    matched_rule_id=rule.rule_id,
                    fast_path=True,
                    as_of_date=as_of_date,
                )
        return None

    def _classify_normalized_query(
        self,
        query: str,
        *,
        query_id: str | None,
        as_of_date: str | date | datetime | None,
    ) -> RouteDecision:
        hngd_match = any(term in query for term in _HNGD_TERMS)
        outside_match = any(term in query for term in _OUT_OF_SCOPE_TERMS)
        explicit_legal = any(term in query for term in _LEGAL_SIGNALS) or bool(
            _LEGAL_CITATION.search(query)
        )
        topic_question = (
            (hngd_match or outside_match)
            and any(marker in query for marker in _LEGAL_QUESTION_MARKERS)
        )

        # A statement about studying law is not itself a request for legal help.
        education_statement = bool(_EDUCATION_STATEMENT.search(query))
        has_request = bool(_EXPLICIT_QUESTION_OR_REQUEST.search(query))
        legal_intent = (explicit_legal or topic_question) and not (
            education_statement and not has_request
        )

        if not legal_intent:
            return RouteDecision(
                query_id=query_id,
                route=Route.NON_LEGAL,
                action=Action.GENERAL_CHAT,
                route_reason=RouteReason.NON_LEGAL_NO_LEGAL_INTENT,
                as_of_date=as_of_date,
            )
        if hngd_match and outside_match:
            return RouteDecision(
                query_id=query_id,
                route=Route.MIXED_LEGAL_SCOPE,
                action=Action.POLICY_ABSTENTION,
                route_reason=RouteReason.MIXED_LEGAL_SCOPE,
                as_of_date=as_of_date,
            )
        if hngd_match:
            return RouteDecision(
                query_id=query_id,
                route=Route.LEGAL_HNGD,
                action=Action.LEGAL_RETRIEVAL,
                route_reason=RouteReason.HNGD_DOMAIN_MATCH,
                as_of_date=as_of_date,
            )
        if outside_match:
            return RouteDecision(
                query_id=query_id,
                route=Route.LEGAL_OUT_OF_SCOPE,
                action=Action.POLICY_ABSTENTION,
                route_reason=RouteReason.LEGAL_OUT_OF_SCOPE_MATCH,
                as_of_date=as_of_date,
            )
        return RouteDecision(
            query_id=query_id,
            route=Route.LEGAL_SCOPE_UNCERTAIN,
            action=Action.POLICY_ABSTENTION,
            route_reason=RouteReason.LEGAL_SCOPE_UNCERTAIN,
            as_of_date=as_of_date,
        )

