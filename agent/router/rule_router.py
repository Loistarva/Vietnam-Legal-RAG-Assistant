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


CLASSIFIER_VERSION = "rule_router_v3"
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


def strip_vietnamese_diacritics(value: str) -> str:
    """Return a comparison form for common Vietnamese queries without accents."""
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_marks.replace("đ", "d")


def _has_any_term(query: str, unaccented_query: str, terms: Sequence[str]) -> bool:
    def has_phrase(text: str, term: str) -> bool:
        normalized_text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()
        normalized_term = re.sub(r"[^\w]+", " ", term, flags=re.UNICODE).strip()
        return f" {normalized_term} " in f" {normalized_text} "

    return any(
        has_phrase(query, term.casefold())
        or has_phrase(unaccented_query, strip_vietnamese_diacritics(term))
        for term in terms
    )


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
    "quyền yêu cầu",
    "khởi kiện",
    "bồi thường",
    "khiếu nại",
    "kháng cáo",
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
    "ly dị",
    "ly thân",
    "lấy vợ",
    "lấy chồng",
    "lấy nhau",
    "cưới nhau",
    "đồng giới",
    "quyền nuôi con",
    "người trực tiếp nuôi",
    "nguyện vọng của con",
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
    "hôn nhân có yếu tố nước ngoài",
    "vợ chồng",
    "thời kỳ hôn nhân",
    "tài sản chung",
    "tài sản riêng",
    "của chung",
    "nuôi con",
    "thăm nom",
    "con nuôi",
    "con riêng",
    "bố dượng",
    "mẹ kế",
    "nhận cha, mẹ, con",
    "nhận cha mẹ con",
    "hộ tịch",
    "khai sinh",
    "người thứ ba ngay tình",
    "trách nhiệm liên đới",
    "hạn chế quyền đối với con chưa thành niên",
    "tình trạng hôn nhân",
    "án phí ly hôn",
    "công nhận thuận tình ly hôn",
    "quyền thăm nom",
    "tảo hôn",
    "ngoài giá thú",
    "giá thú",
    "xác định cha",
    "xác định mẹ",
)
_HNGD_CONTEXTUAL_SIGNAL = re.compile(
    r"\b(?:bao nhiêu tuổi|độ tuổi|tuổi tối thiểu)\b.{0,60}"
    r"\b(?:được\s+)?(?:cưới|kết hôn|lấy vợ|lấy chồng)\b"
    r"|"
    r"\b(?:cưới|kết hôn|lấy vợ|lấy chồng)\b.{0,60}"
    r"\b(?:bao nhiêu tuổi|độ tuổi|tuổi tối thiểu)\b",
    re.IGNORECASE,
)
_HNGD_CONTEXTUAL_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_HNGD_CONTEXTUAL_SIGNAL.pattern), re.IGNORECASE
)

_OUT_OF_SCOPE_TERMS = (
    "nợ lương",
    "nợ tiền lương",
    "hàng xóm xây nhà lấn",
    "lấn sang đất",
    "cho vay tiền",
    "đòi nợ",
    "mua hàng online bị lừa",
    "báo công an",
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
    "phạm tội",
    "đi tù",
    "phạt tù",
    "truy cứu trách nhiệm hình sự",
    "trộm cắp",
    "lừa đảo",
    "gây thương tích",
    "tiền cọc",
    "thuê nhà",
    "chủ nhà không trả tiền cọc",
    "tranh chấp tiền đặt cọc",
    "lừa chuyển khoản",
    "bị lừa chuyển khoản",
    "chiếm đoạt tiền",
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
    "thửa đất",
    "ranh giới đất",
    "tranh chấp đất",
    "đất đai",
    "thừa kế",
    "di chúc",
    "di sản",
    "tranh chấp bảo hành",
    "từ chối bảo hành",
    "bảo vệ quyền lợi người tiêu dùng",
    "quyền lợi người tiêu dùng",
    "tranh chấp tiêu dùng",
    "thành lập doanh nghiệp",
    "doanh nghiệp",
    "vượt đèn đỏ",
    "xử phạt hành chính",
    "khung hình phạt",
)

_EDUCATION_STATEMENT = re.compile(
    r"\b(?:tôi|em|mình)\s+(?:đang\s+)?(?:học|nghiên cứu)\s+(?:môn\s+)?luật\b"
)
_EDUCATION_STATEMENT_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_EDUCATION_STATEMENT.pattern), re.IGNORECASE
)
_EXPLICIT_QUESTION_OR_REQUEST = re.compile(
    r"\?|\b(?:là gì|thế nào|ra sao|giải thích|cho biết|tư vấn|tìm hiểu|"
    r"hỏi(?:\s+(?:về|thêm))?|có được|điều kiện|quyền gì|nghĩa vụ gì|bao lâu|bao nhiêu)\b"
)
_LEGAL_CITATION = re.compile(r"\b(?:điều|khoản)\s+\d+\b")
_LEGAL_DOCUMENT_REFERENCE = re.compile(
    r"\b(?:luật|nghị\s+định|thông\s+tư|nghị\s+quyết|pháp\s+lệnh|văn\s+bản|nđ|tt|nq)\s+"
    r"(?:số\s+)?(?:\d{1,4}[a-zđ]?(?:[./-][\wđ-]+)*|\d{4})\b",
    re.IGNORECASE,
)
_CONTEXTUAL_LEGAL_SIGNAL = re.compile(
    r"\b(?:tôi|em|mình|người đó|đương sự)?\s*(?:có quyền|được quyền)\s+"
    r"(?:yêu cầu|khởi kiện|bồi thường|khiếu nại|kháng cáo|nuôi con|ly hôn|"
    r"đăng ký kết hôn|chia tài sản)\b"
    r"|\b(?:hồ sơ|thủ tục)\s+(?:đăng ký kết hôn|kết hôn|ly hôn|khởi kiện|"
    r"khởi kiện tại tòa án|nhận cha mẹ con|nhận cha, mẹ, con)\b"
    r"|\b(?:nộp|gửi)\s+(?:đơn|hồ sơ)\s+(?:tại|lên)\s+tòa(?:\s+án)?\b"
    r"|\bkhởi kiện\s+(?:tại|lên)\s+tòa(?:\s+án)?\b",
    re.IGNORECASE,
)
_CONTEXTUAL_LEGAL_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_CONTEXTUAL_LEGAL_SIGNAL.pattern), re.IGNORECASE
)
_NEGATED_HNGD_SCOPE = re.compile(
    r"\bkhông\s+có\s+(?:tranh\s+chấp\s+)?(?:tài\s+sản\s+)?"
    r"(?:vợ\s+chồng|hôn\s+nhân|gia\s+đình)\b",
    re.IGNORECASE,
)
_CLEAR_NONLEGAL_SIGNAL = re.compile(
    r"\b(?:xin chào|chào bạn|thời tiết|nhiệt độ|mưa hôm nay|"
    r"hồ sơ xin việc|thủ tục nhập học|(?:viết (?:giúp tôi )?(?:một )?)?(?:bài thơ|lời chúc)|"
    r"email xin nghỉ phép|"
    r"mua quà sinh nhật|gợi ý (?:một )?quà sinh nhật|quà sinh nhật|"
    r"giải thích (?:thuật toán|binary search)|"
    r"(?:hướng dẫn )?học (?:python|lập trình)|lập lịch học|công thức nấu|món ăn|nấu món|"
    r"kể (?:một )?câu chuyện|câu chuyện vui|lịch trình du lịch|gợi ý du lịch|"
    r"dịch (?:câu|đoạn văn)|giải phương trình|đạo hàm|bài tập toán|"
    r"đánh giá (?:điện thoại|máy tính)|cách trồng cây|chăm sóc cây)\b",
    re.IGNORECASE,
)
_CLEAR_NONLEGAL_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_CLEAR_NONLEGAL_SIGNAL.pattern), re.IGNORECASE
)
_SOCIAL_NONLEGAL_SIGNAL = re.compile(
    r"^\s*(?:"
    r"xin chào(?: bạn)?"
    r"|chào(?: bạn| buổi sáng| buổi chiều| buổi tối)?"
    r"|cảm ơn(?: bạn)?(?: nhé)?"
    r"|thanks"
    r"|thank you"
    r"|tạm biệt"
    r")[!.?\s]*$",
    re.IGNORECASE,
)
_SOCIAL_NONLEGAL_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_SOCIAL_NONLEGAL_SIGNAL.pattern), re.IGNORECASE
)
_GENERAL_KNOWLEDGE_SIGNAL = re.compile(
    r"^\s*thủ đô\s+(?:của\s+)?[\w\s]+?\s+là gì\s*[?!.]?\s*$",
    re.IGNORECASE,
)
_GENERAL_KNOWLEDGE_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_GENERAL_KNOWLEDGE_SIGNAL.pattern), re.IGNORECASE
)
_GENERAL_ENTERTAINMENT_SIGNAL = re.compile(
    r"^\s*(?:hãy\s+)?(?:kể|nói)\s+(?:cho tôi\s+)?(?:một\s+)?"
    r"(?:câu chuyện|chuyện|câu)\s+cười(?:\s+.*)?[!.?]?\s*$",
    re.IGNORECASE,
)
_GENERAL_ENTERTAINMENT_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_GENERAL_ENTERTAINMENT_SIGNAL.pattern), re.IGNORECASE
)
_GENERAL_BANKING_SIGNAL = re.compile(
    r"^\s*(?:(?:hướng dẫn|cách)\s+)?chuyển khoản\s+"
    r"(?:(?:qua\s+)?ngân hàng(?:\s+(?:như thế nào|ra sao))?|cho bạn bè)"
    r"(?:\s+(?:như thế nào|ra sao))?[.!?]*\s*$",
    re.IGNORECASE,
)
_GENERAL_BANKING_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_GENERAL_BANKING_SIGNAL.pattern), re.IGNORECASE
)
_INDEPENDENT_OUTSIDE_TOPIC = re.compile(
    r"\b(?:và|đồng thời|ngoài ra|cùng với|kèm theo)\b.{0,100}\b(?:"
    r"thuế|hình sự|hợp đồng lao động|doanh nghiệp|tranh chấp đất(?: đai)?|"
    r"tranh chấp thừa kế|phân chia di sản|di chúc)\b"
    r"|\b(?:tranh chấp đất(?: đai)?|phân chia di sản|tranh chấp thừa kế)\b",
    re.IGNORECASE,
)
_INDEPENDENT_OUTSIDE_TOPIC_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_INDEPENDENT_OUTSIDE_TOPIC.pattern), re.IGNORECASE
)


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
        unaccented_query = strip_vietnamese_diacritics(query)
        hngd_match = (
            _has_any_term(query, unaccented_query, _HNGD_TERMS)
            or bool(_HNGD_CONTEXTUAL_SIGNAL.search(query))
            or bool(_HNGD_CONTEXTUAL_SIGNAL_UNACCENTED.search(unaccented_query))
        )
        # A negated family-scope phrase used to clarify that a different
        # dispute is unrelated must not turn that dispute into an HNGD query.
        without_negated_hngd = _NEGATED_HNGD_SCOPE.sub(" ", query)
        if without_negated_hngd != query and not _has_any_term(
            without_negated_hngd,
            strip_vietnamese_diacritics(without_negated_hngd),
            _HNGD_TERMS,
        ):
            hngd_match = False
        outside_match = _has_any_term(query, unaccented_query, _OUT_OF_SCOPE_TERMS)
        explicit_legal = _has_any_term(query, unaccented_query, _LEGAL_SIGNALS) or bool(
            _LEGAL_CITATION.search(query)
            or _LEGAL_CITATION.search(unaccented_query)
            or _LEGAL_DOCUMENT_REFERENCE.search(query)
            or _LEGAL_DOCUMENT_REFERENCE.search(unaccented_query)
            or _CONTEXTUAL_LEGAL_SIGNAL.search(query)
            or _CONTEXTUAL_LEGAL_SIGNAL_UNACCENTED.search(unaccented_query)
        )
        family_relation_context = _has_any_term(
            query,
            unaccented_query,
            ("vợ", "chồng", "vợ chồng", "hôn nhân", "ly hôn", "ly dị", "ly thân",
             "con nuôi", "con riêng", "bố dượng", "mẹ kế"),
        )
        property_context = _has_any_term(
            query,
            unaccented_query,
            ("tài sản", "lương", "lao động", "vốn góp", "quyền sử dụng đất",
             "thừa kế", "di sản"),
        )
        spouse_death_context = (
            _has_any_term(query, unaccented_query, ("vợ", "chồng"))
            and _has_any_term(query, unaccented_query, ("mất", "chết", "qua đời", "từ trần"))
            and _has_any_term(
                query,
                unaccented_query,
                ("nhà", "đất", "tài sản", "di sản", "thừa kế", "để lại", "đứng tên"),
            )
        )
        if spouse_death_context:
            hngd_match = True
            outside_match = True
        hngd_property_context = (
            (family_relation_context and property_context)
            or _has_any_term(query, unaccented_query, ("thời kỳ hôn nhân",))
            or (
                _has_any_term(query, unaccented_query, ("tài sản chung",))
                and _has_any_term(query, unaccented_query, ("quyền sử dụng đất",))
            )
        )
        independent_outside_topic = bool(
            _INDEPENDENT_OUTSIDE_TOPIC.search(query)
            or _INDEPENDENT_OUTSIDE_TOPIC_UNACCENTED.search(unaccented_query)
        )
        if (
            hngd_match
            and hngd_property_context
            and not independent_outside_topic
            and not spouse_death_context
        ):
            outside_match = False
        # A statement about studying law is not itself a request for legal help.
        education_statement = bool(
            _EDUCATION_STATEMENT.search(query)
            or _EDUCATION_STATEMENT_UNACCENTED.search(unaccented_query)
        )
        has_request = bool(_EXPLICIT_QUESTION_OR_REQUEST.search(query))
        clear_nonlegal = (education_statement and not has_request) or any(
            signal.search(text)
            for signal, text in (
                (_CLEAR_NONLEGAL_SIGNAL, query),
                (_CLEAR_NONLEGAL_SIGNAL_UNACCENTED, unaccented_query),
                (_SOCIAL_NONLEGAL_SIGNAL, query),
                (_SOCIAL_NONLEGAL_SIGNAL_UNACCENTED, unaccented_query),
                (_GENERAL_KNOWLEDGE_SIGNAL, query),
                (_GENERAL_KNOWLEDGE_SIGNAL_UNACCENTED, unaccented_query),
                (_GENERAL_ENTERTAINMENT_SIGNAL, query),
                (_GENERAL_ENTERTAINMENT_SIGNAL_UNACCENTED, unaccented_query),
                (_GENERAL_BANKING_SIGNAL, query),
                (_GENERAL_BANKING_SIGNAL_UNACCENTED, unaccented_query),
            )
        )
        # A clear general-chat phrase must never erase a legal request in the
        # same query. Treat a legal topic plus an explicit question/request as
        # mixed intent; abstain so the system cannot answer the whole prompt as
        # unrestricted chat. Bare incidental mentions (for example, a poem
        # "about divorce") remain general chat.
        has_legal_request = outside_match or explicit_legal or (hngd_match and has_request)
        if clear_nonlegal and has_legal_request:
            return RouteDecision(
                query_id=query_id,
                route=Route.MIXED_LEGAL_SCOPE,
                action=Action.POLICY_ABSTENTION,
                route_reason=RouteReason.MIXED_LEGAL_SCOPE,
                as_of_date=as_of_date,
            )
        if clear_nonlegal and not has_legal_request:
            return RouteDecision(
                query_id=query_id,
                route=Route.NON_LEGAL,
                action=Action.GENERAL_CHAT,
                route_reason=RouteReason.NON_LEGAL_NO_LEGAL_INTENT,
                as_of_date=as_of_date,
            )
        # A recognized legal topic is itself sufficient intent. Requiring a
        # question marker misroutes yes/no and procedural questions to chat.
        legal_intent = (hngd_match or outside_match or explicit_legal) and not (
            education_statement and not has_request
        )

        if not legal_intent:
            return RouteDecision(
                query_id=query_id,
                route=Route.LEGAL_SCOPE_UNCERTAIN,
                action=Action.LEGAL_RETRIEVAL,
                route_reason=RouteReason.LEGAL_SCOPE_UNCERTAIN,
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
            action=Action.LEGAL_RETRIEVAL,
            route_reason=RouteReason.LEGAL_SCOPE_UNCERTAIN,
            as_of_date=as_of_date,
        )

