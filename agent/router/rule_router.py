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


CLASSIFIER_VERSION = "rule_router_v5"
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

    def to_canonical(self):
        """Convert the Dev4 decision to the canonical Dev3 Pydantic contract."""
        from schemas.models import RouteDecision as CanonicalRouteDecision
        from schemas.models import map_router_route_to_canonical

        explanations = {
            RouteReason.FAST_PATH_RULE_MATCH: "Câu hỏi khớp chính xác quy tắc fast-path đã được phê duyệt.",
            RouteReason.HNGD_DOMAIN_MATCH: "Câu hỏi thuộc phạm vi Hôn nhân và Gia đình.",
            RouteReason.LEGAL_OUT_OF_SCOPE_MATCH: "Câu hỏi pháp lý nằm ngoài phạm vi Hôn nhân và Gia đình.",
            RouteReason.LEGAL_SCOPE_UNCERTAIN: "Chưa đủ thông tin để xác định chính xác phạm vi pháp lý.",
            RouteReason.MIXED_LEGAL_SCOPE: "Câu hỏi kết hợp phạm vi Hôn nhân và Gia đình với lĩnh vực pháp lý khác.",
            RouteReason.NON_LEGAL_NO_LEGAL_INTENT: "Câu hỏi không thể hiện ý định yêu cầu thông tin pháp lý.",
            RouteReason.INVALID_EMPTY_QUERY: "Câu hỏi rỗng.",
            RouteReason.INVALID_QUERY_TYPE: "Kiểu dữ liệu câu hỏi không hợp lệ.",
            RouteReason.INVALID_AS_OF_DATE: "Ngày áp dụng không hợp lệ.",
        }
        as_of_date = self.as_of_date
        if isinstance(as_of_date, (date, datetime)):
            as_of_date = as_of_date.isoformat()
        return CanonicalRouteDecision(
            route=map_router_route_to_canonical(self.route.value),
            reason_code=self.route_reason.value,
            explanation=explanations[self.route_reason],
            policy_version=self.classifier_version,
            query_id=self.query_id,
            action=self.action.value,
            matched_rule_id=self.matched_rule_id,
            fast_path=self.fast_path,
            as_of_date=as_of_date,
        )

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


_HNGD_FAMILY_RELATIONS = (
    "anh chị em", "anh em ruột", "chị em ruột", "ông bà", "ông bà nội",
    "ông bà ngoại", "cha mẹ", "bố mẹ", "cha mẹ đẻ", "cha mẹ nuôi",
    "con chưa thành niên", "con nuôi", "con riêng", "bố dượng", "mẹ kế",
    "người phối ngẫu", "người vợ cũ", "người chồng cũ",
    "thành viên gia đình", "thành viên trong gia đình", "người trong gia đình",
)
_HNGD_FAMILY_TOPICS = (
    "nuôi dưỡng", "chăm sóc", "chăm sóc con", "giáo dục", "phụng dưỡng",
    "cấp dưỡng", "chu cấp", "hỗ trợ tài chính", "hỗ trợ về vật chất",
    "đại diện", "giám hộ", "danh dự", "nhân phẩm", "uy tín",
    "trách nhiệm gia đình", "quyền lợi của con", "quyền lợi của các con",
    "bảo vệ con", "thay đổi người trực tiếp nuôi con", "trực tiếp chăm sóc con",
    "lấy ý kiến của con", "lấy ý kiến của cha mẹ", "cho con làm con nuôi",
)
_HNGD_LEGAL_CONTEXT = (
    "pháp luật", "theo quy định", "quyền", "nghĩa vụ", "trách nhiệm",
    "trường hợp", "quy định", "phải", "có được", "được quyền", "nguyên tắc",
    "điều kiện", "giải quyết", "thủ tục", "bất đồng", "tranh chấp",
)


def _has_contextual_hngd_signal(query: str, unaccented_query: str) -> bool:
    """Require family relationship + family-law topic + legal context.

    This avoids treating words such as ``đại diện`` or ``giám hộ`` alone as
    sufficient proof that a question belongs to family law.
    """
    return (
        _has_any_term(query, unaccented_query, _HNGD_FAMILY_RELATIONS)
        and _has_any_term(query, unaccented_query, _HNGD_FAMILY_TOPICS)
        and _has_any_term(query, unaccented_query, _HNGD_LEGAL_CONTEXT)
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
    "tài sản chung",
    "tài sản riêng",
    "của chung",
    "tài sản chung là quyền sử dụng đất",
    "tiền lương của chồng",
    "lương của chồng",
    "lao động của vợ trong gia đình",
    "lao động của vợ khi chia tài sản chung",
    "quan hệ vợ chồng",
    "quyền và nghĩa vụ của vợ chồng",
    "xác định cha, mẹ, con",
    "xác định cha mẹ con",
    "mang thai hộ",
    "kết hôn với người nước ngoài",
    "hôn nhân có yếu tố nước ngoài",
    "vợ chồng",
    "thời kỳ hôn nhân",
    "thăm nom",
    "nuôi con",
    "con nuôi",
    "con riêng",
    "bố dượng",
    "mẹ kế",
    "nhận cha, mẹ, con",
    "nhận cha mẹ con",
    "đăng ký khai sinh cho con",
    "thủ tục đăng ký khai sinh",
    "cha muốn nhận con",
    "cha nhận con",
    "hạn chế quyền đối với con chưa thành niên",
    "tòa án hạn chế quyền cha mẹ",
    "hạn chế quyền của cha mẹ đối với con",
    "hạn chế quyền cha mẹ đối với con",
    "cha mẹ bị hạn chế quyền đối với con",
    "quyền của cha mẹ đối với con chưa thành niên",
    "vợ chồng đại diện cho nhau",
    "vợ đại diện cho chồng",
    "chồng đại diện cho vợ",
    "vợ có được đại diện cho chồng",
    "chồng có được đại diện cho vợ",
    "vợ hoặc chồng có thể đại diện",
    "một bên vợ hoặc chồng đại diện cho bên kia",
    "đại diện cho nhau trong giao dịch",
    "đại diện cho nhau trong hoạt động kinh doanh",
    "đại diện giữa vợ và chồng",
    "một bên vợ chồng đại diện",
    "giao dịch do vợ chồng xác lập",
    "kinh doanh chung của vợ chồng",
    "hoạt động kinh doanh chung của vợ chồng",
    "một bên vợ hoặc chồng không thể tự mình xác lập giao dịch",
    "bên kia có thể đại diện trong trường hợp nào",
    "vợ hoặc chồng có thể nhân danh người kia thực hiện giao dịch",
    "giao dịch liên quan đến hoạt động kinh doanh chung",
    "tài sản chung trong kinh doanh",
    "tài sản chung và nghĩa vụ chung",
    "thỏa thuận chia tài sản chung",
    "người thứ ba ngay tình",
    "trách nhiệm liên đới",
    "tình trạng hôn nhân",
    "án phí ly hôn",
    "công nhận thuận tình ly hôn",
    "quyền thăm nom",
    "tảo hôn",
    "ngoài giá thú",
    "giá thú",
    "xác định cha",
    "xác định mẹ",
    "xác định quan hệ cha con",
    "yêu cầu xác định cha con",
    "yêu cầu tòa án xác định quan hệ cha con",
    "quan hệ hôn nhân",
    "tự do tín ngưỡng giữa vợ chồng",
    "tín ngưỡng giữa vợ chồng",
    "tôn giáo giữa vợ chồng",
    "quyết định việc học của con",
    "chọn trường cho con",
    "chuyển con sang trường",
    "chồng đưa con",
    "cha mẹ đưa con",
    "người phối ngẫu",
    "cùng giới tính",
    "kỹ thuật hỗ trợ sinh sản",
    "hỗ trợ sinh sản",
    "noãn hiến",
    "tinh trùng hiến",
    "thụ tinh trong ống nghiệm",
    "làm con nuôi",
    "nhận con nuôi",
    "cho con làm con nuôi",
    "cha mẹ nuôi",
    "cha dượng",
)
_HNGD_CONTEXTUAL_SIGNAL = re.compile(
    r"\b(?:bao nhiêu tuổi|độ tuổi|tuổi tối thiểu)\b.{0,60}"
    r"\b(?:được\s+)?(?:cưới|kết hôn|lấy vợ|lấy chồng)\b"
    r"|"
    r"\b(?:cưới|kết hôn|lấy vợ|lấy chồng)\b.{0,60}"
    r"\b(?:bao nhiêu tuổi|độ tuổi|tuổi tối thiểu)\b"
    r"|"
    r"\b(?:xác định|nhận|chối bỏ)\b.{0,30}\b(?:mình là\s+)?(?:cha|mẹ|con)\b"
    r"|"
    r"\b(?:cùng giới tính|đồng giới)\b.{0,60}\b(?:chung sống|kết hôn|công nhận quan hệ|hộ tịch)\b"
    r"|"
    r"\b(?:chung sống|thời gian sống riêng)\b.{0,80}\b(?:hỗ trợ tài chính|cấp dưỡng|vợ chồng|ly hôn)\b",
    re.IGNORECASE,
)
_HNGD_CONTEXTUAL_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_HNGD_CONTEXTUAL_SIGNAL.pattern), re.IGNORECASE
)
_HNGD_DOMESTIC_VIOLENCE_PROTECTIVE_SIGNAL = re.compile(
    r"\b(?:bạo lực gia đình.{0,140}(?:cấm tiếp xúc|biện pháp bảo vệ)|"
    r"(?:cấm tiếp xúc|biện pháp bảo vệ).{0,140}bạo lực gia đình)\b",
    re.IGNORECASE,
)
_HNGD_DOMESTIC_VIOLENCE_PROTECTIVE_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_HNGD_DOMESTIC_VIOLENCE_PROTECTIVE_SIGNAL.pattern),
    re.IGNORECASE,
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
    "phạt tù bao nhiêu",
    "đi tù mấy năm",
    "hình phạt tù",
    "mức án phạt tù",
)

# Topic groups use contextual legal phrases, not isolated words. Keeping these
# grouped makes domain coverage reviewable and reduces accidental matches.
_OUT_OF_SCOPE_TOPIC_GROUPS = {
    "intellectual_property": (
        "quyền tác giả", "bản quyền tác phẩm", "nhãn hiệu đã đăng ký",
        "sở hữu trí tuệ", "sáng chế được bảo hộ", "xâm phạm nhãn hiệu",
    ),
    "immigration": (
        "xin visa", "visa nhập cảnh", "thủ tục visa", "thủ tục xin visa",
        "thủ tục xin cấp thị thực", "xin cấp thị thực", "thị thực nhập cảnh",
        "người nước ngoài nhập cảnh", "nhập cảnh việt nam", "đăng ký cư trú",
        "đưa trẻ ra nước ngoài", "đưa con ra nước ngoài", "du học ở nước ngoài",
    ),
    "labor": (
        "thời giờ làm thêm", "giới hạn làm thêm giờ", "làm thêm giờ",
        "tăng ca theo luật lao động", "hợp đồng lao động",
    ),
    "tax": (
        "kê khai và nộp thuế", "nghĩa vụ kê khai thuế", "nộp thuế",
        "thuế kinh doanh trực tuyến", "nghĩa vụ thuế",
        "thuế chuyển nhượng", "thuế khi chuyển nhượng",
        "thuế chuyển nhượng bất động sản", "thuế thu nhập từ chuyển nhượng",
        "kê khai thuế chuyển nhượng", "nộp thuế chuyển nhượng",
    ),
    "traffic": (
        "không đội mũ bảo hiểm", "xử phạt vi phạm giao thông",
        "quyết định xử phạt", "giấy phép lái xe", "biên bản vi phạm giao thông",
        "xử phạt nồng độ cồn", "vi phạm nồng độ cồn", "mức phạt nồng độ cồn",
        "lái xe sau khi uống rượu bia", "điều khiển phương tiện sau khi uống rượu bia",
        "điều khiển xe sau khi sử dụng rượu bia", "đã uống rượu bia khi lái xe",
        "lái xe sau khi uống rượu",
    ),
    "environment": (
        "quy chuẩn tiếng ồn", "tiếng ồn vượt quy chuẩn", "ô nhiễm môi trường",
        "xả khí thải", "xả thải gây ô nhiễm", "xử phạt môi trường",
    ),
    "banking_and_credit": (
        "phong tỏa tài khoản", "tài khoản thanh toán", "pháp luật ngân hàng",
        "hoạt động ngân hàng", "vay vốn ngân hàng", "hợp đồng tín dụng",
        "khoản vay ngân hàng", "nghĩa vụ trả nợ ngân hàng",
    ),
    "construction": (
        "cơi nới ban công", "thay đổi kết cấu chịu lực", "giấy phép xây dựng",
        "pháp luật xây dựng",
    ),
    "cybersecurity": (
        "chiếm quyền truy cập tài khoản", "chiếm quyền tài khoản",
        "xâm nhập trái phép tài khoản", "tài khoản mạng xã hội",
    ),
    "data_protection": (
        "bảo vệ dữ liệu cá nhân", "dữ liệu cá nhân", "dữ liệu vị trí",
        "chia sẻ dữ liệu cá nhân", "tiết lộ hồ sơ bệnh án",
    ),
    "education": (
        "buộc thôi học", "quyết định kỷ luật sinh viên", "kỷ luật sinh viên",
        "pháp luật giáo dục đại học", "đình chỉ học", "quyết định đình chỉ học",
    ),
    "healthcare": (
        "trách nhiệm của cơ sở y tế", "trách nhiệm cơ sở y tế",
        "cơ sở khám chữa bệnh",
        "chấp thuận phẫu thuật", "đồng ý phẫu thuật", "lưu trữ phôi",
        "quy trình chuyên môn của bệnh viện",
    ),
    "public_procurement": (
        "pháp luật đấu thầu", "nhà thầu bị loại", "kiến nghị kết quả đánh giá",
        "kết quả lựa chọn nhà thầu", "hồ sơ mời thầu",
    ),
    "civil_status": (
        "pháp luật hộ tịch", "đăng ký hộ tịch",
        "cập nhật thông tin trên giấy khai sinh", "từ chối cập nhật giấy khai sinh",
        "cải chính hộ tịch",
    ),
    "aviation_and_transport": (
        "hãng hàng không", "vận chuyển hành khách", "từ chối vận chuyển",
        "chuyến bay", "vận tải hàng không", "vận tải đường sắt",
        "vận tải đường bộ", "quyền lợi hành khách",
    ),
    "postal_and_logistics": (
        "bưu gửi", "bưu phẩm", "đơn vị chuyển phát", "dịch vụ bưu chính",
        "chuyển phát hàng hóa", "thất lạc hàng",
    ),
    "mining_and_geology": (
        "khai thác khoáng sản", "khai thác đá", "giấy phép khai thác",
        "luật khoáng sản", "mỏ khoáng sản",
    ),
    "fisheries_and_maritime": (
        "tàu cá", "khai thác thủy sản", "pháp luật thủy sản",
        "quy định thủy sản", "luật thủy sản", "thiết bị khai thác bị cấm",
        "vùng biển không được phép",
    ),
    "fire_safety": (
        "phòng cháy", "chữa cháy", "báo cháy", "hệ thống báo cháy",
        "điều kiện phòng cháy", "an toàn phòng cháy", "hỏa hoạn",
    ),
    "civil_service_and_public_duty": (
        "công chức", "viên chức", "cán bộ công chức",
        "hồ sơ công vụ", "bí mật công vụ", "kỷ luật công chức",
        "xử lý kỷ luật",
    ),
    "veterinary_and_quarantine": (
        "kiểm dịch động vật", "giấy chứng nhận kiểm dịch",
        "quy định thú y", "pháp luật thú y", "luật thú y",
        "kiểm dịch thực vật", "vận chuyển gia súc",
    ),
    "sports_and_antidoping": (
        "vận động viên", "giải thi đấu", "chất nằm trong danh mục cấm",
        "dùng chất cấm", "quy định thể thao", "pháp luật thể thao",
    ),
    "maritime_telecom_commerce": (
        "hàng hải", "tàu biển", "cảng vụ", "vận tải biển",
        "viễn thông", "nhà mạng", "sim rác", "tần số vô tuyến",
        "xuất khẩu", "nhập khẩu", "thương nhân", "cạnh tranh không lành mạnh",
        "tập trung kinh tế", "kinh doanh xuất khẩu", "chống bán phá giá",
    ),
    "insolvency": (
        "mất khả năng thanh toán", "thủ tục phá sản", "mở thủ tục phá sản",
        "yêu cầu mở thủ tục phá sản", "chủ nợ nộp đơn phá sản",
    ),
    "securities_market": (
        "công ty đại chúng", "công bố thông tin sai lệch", "ngày chốt quyền",
        "nhận cổ tức", "giao dịch nội gián", "thị trường chứng khoán",
    ),
    "food_safety": (
        "an toàn thực phẩm", "thực phẩm nhiễm khuẩn", "ngộ độc thực phẩm",
        "cơ sở chế biến thực phẩm", "thực phẩm không bảo đảm an toàn",
    ),
    "pharmaceutical_regulation": (
        "thuốc kê đơn", "đơn thuốc hợp lệ", "bán thuốc không có đơn",
        "nhà thuốc bán thuốc", "quy định về dược",
    ),
    "water_resources": (
        "khai thác nước ngầm", "lưu lượng được cấp phép", "giấy phép khai thác nước",
        "khai thác nước vượt giấy phép", "tài nguyên nước",
    ),
    "occupational_safety": (
        "tai nạn lao động", "an toàn lao động", "bồi thường tai nạn lao động",
        "máy móc tại nơi làm việc", "tai nạn tại nơi làm việc",
        "sử dụng lao động chưa đủ tuổi", "lao động chưa đủ tuổi",
    ),
    "secured_transactions": (
        "tài sản bảo đảm", "xử lý tài sản bảo đảm", "dùng nhà làm tài sản bảo đảm",
        "thế chấp nhà bảo đảm khoản vay", "ngân hàng xử lý tài sản",
    ),
    "corporate": (
        "công ty trách nhiệm hữu hạn", "công ty tnhh", "thành viên công ty tnhh",
        "chào bán phần vốn góp", "chào bán vốn góp", "tranh chấp phần vốn góp",
        "tranh chấp vốn góp", "chuyển nhượng phần vốn góp", "chuyển nhượng vốn góp",
        "mua lại phần vốn góp", "thành viên góp vốn", "góp vốn vào công ty",
        "phần vốn góp trong công ty", "quyền biểu quyết thành viên",
        "quyền biểu quyết của thành viên", "cổ phần doanh nghiệp",
        "cổ phần trong công ty", "tranh chấp cổ phần", "chuyển nhượng cổ phần",
        "quyền biểu quyết của cổ đông", "cổ đông công ty",
    ),
    "land_acquisition": (
        "thu hồi đất", "quyết định thu hồi đất", "đất đang bị thu hồi",
        "tranh chấp đất với hàng xóm", "tranh chấp ranh giới đất",
        "hàng xóm lấn đất", "hàng xóm lấn sang đất", "ranh giới đất với hàng xóm",
        "lấn chiếm đất của hàng xóm", "tranh chấp mốc giới đất",
        "đất đang có tranh chấp với hàng xóm",
    ),
    "consumer_protection": (
        "luật bảo vệ quyền lợi người tiêu dùng",
        "theo luật bảo vệ quyền lợi người tiêu dùng",
        "yêu cầu bồi thường theo luật bảo vệ quyền lợi người tiêu dùng",
        "bồi thường cho người tiêu dùng", "người tiêu dùng yêu cầu bồi thường",
        "người tiêu dùng có thể yêu cầu bồi thường", "mua phải hàng hóa lỗi",
        "hàng hóa lỗi theo quy định", "yêu cầu bồi thường khi mua phải hàng hóa lỗi",
        "hàng hóa có khuyết tật", "sản phẩm bị lỗi gây thiệt hại",
        "tranh chấp với bên bán hàng",
    ),
    "criminal_property": (
        "hành vi chiếm đoạt tài sản", "tội chiếm đoạt tài sản",
        "lừa đảo chiếm đoạt tài sản", "chiếm đoạt tiền",
        "chiếm đoạt tài sản", "bị chiếm đoạt tài sản",
    ),
}


def _has_out_of_scope_topic(query: str, unaccented_query: str) -> bool:
    return any(
        _has_any_term(query, unaccented_query, phrases)
        for phrases in _OUT_OF_SCOPE_TOPIC_GROUPS.values()
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
    r"\b(?:xin chào|thời tiết|nhiệt độ|mưa hôm nay|"
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
_PRACTICAL_NONLEGAL_INTENTS = (
    # Programming, software, and office-tool usage requests.
    re.compile(
        r"\b(?:viết|tạo|sửa|debug|xây dựng|thiết kế|làm)\s+(?:(?:giúp\s+)?(?:tôi|em|mình)\s+)?"
        r"(?:(?:một|một đoạn|một bảng)\s+)?(?:đoạn\s+)?(?:mã|code|hàm|chương trình|bảng tính|bảng excel)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:hàm|vòng lặp|loop|python|mã nguồn|thuật toán)\b.{0,60}"
        r"\b(?:python|for|while|lập trình|chạy thử|debug|duyệt|đồ thị|ví dụ)\b",
        re.IGNORECASE,
    ),
    # Everyday study plans, learning languages, music, photography, crafts, DIY, and sports/fitness.
    re.compile(
        r"\b(?:lập|lên|xếp|tạo)\s+(?:cho\s+(?:tôi|em|mình)\s+)?"
        r"(?:kế hoạch|lịch(?:\s+(?:tự\s+)?học|\s+ôn|\s+tham quan|\s+du lịch)?|danh sách)\b"
        r"(?:.{0,80}\b(?:tham quan|du lịch|đi chơi|cắm trại|học|ôn|mỗi ngày|tuần|ngày)\b)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:chuẩn bị|cần chuẩn bị|mang theo)\b.{0,50}\b(?:cắm trại|đi trại|dã ngoại|du lịch|trang phục)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:hướng dẫn|chỉ|gợi ý|cách)\b.{0,60}\b(?:"
        r"chơi\s+(?:cờ|game|nhạc cụ|guitar|piano)|"
        r"tập\s+(?:yoga|thể dục|gym|chạy bộ)|(?:động tác|bài tập)\s+(?:nhẹ|yoga|thể dục)|"
        r"đọc nốt nhạc|đếm nhịp|chọn khẩu độ|tốc độ màn trập|chụp (?:ảnh|chân dung)|"
        r"(?:tự\s+)?(?:làm|may|đóng)\s+(?:túi|đồ gỗ|đồ thủ công|bể thủy sinh)|"
        r"thiết lập\s+bể\s+thủy sinh|chăm sóc cây|trồng\s+(?:cây|rau)|"
        r"pha\s+(?:cà phê|trà|đồ uống)|nấu\s+(?:ăn|món)|làm bánh|"
        r"mạng\s+wi-?fi|điện thoại|máy tính bảng"
        r")\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:làm thế nào|cần những dụng cụ|gợi ý một dự án|mới tập)\b.{0,80}\b(?:"
        r"pha\s+(?:cà phê|trà)|nấu|làm\s+(?:đồ gỗ|túi|bánh)|may|trồng\s+cây|"
        r"tập\s+(?:yoga|thể dục)|chơi\s+cờ|động tác"
        r")\b",
        re.IGNORECASE,
    ),
    # General natural-science, astronomy, weather, and plant-care questions.
    re.compile(
        r"\b(?:vì sao|tại sao|giải thích(?:\s+cách|\s+vì sao)?|cho biết)\b.{0,80}\b(?:"
        r"phát sáng|khí quyển|hiện tượng|sao băng|cầu vồng|mặt trăng|pha trăng|"
        r"wi-?fi|thuật toán|bể thủy sinh|đọc nốt nhạc|đếm nhịp|luyện tập"
        r")\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:cây|lá cây)\b.{0,40}\b(?:vàng lá|héo|rụng lá)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:cách|hướng dẫn|chỉ)\s+(?:(?:tôi|em|mình)\s+)?"
        r"(?:trồng|chăm sóc|gieo trồng|gieo hạt)\s+(?:cây|rau)\b"
        r"|\b(?:trồng|chăm sóc)\s+(?:cây|rau)\s+(?:cảnh|trong chậu|trong nhà|ở ban công|ngoài vườn)\b",
        re.IGNORECASE,
    ),
)
_PRACTICAL_NONLEGAL_INTENTS_UNACCENTED = tuple(
    re.compile(strip_vietnamese_diacritics(pattern.pattern), re.IGNORECASE)
    for pattern in _PRACTICAL_NONLEGAL_INTENTS
)
# Common everyday food/recommendation requests. Keep these patterns bounded to
# ordinary-life intents; do not infer NON_LEGAL from an unknown query alone.
_DAILY_NONLEGAL_INTENTS = (
    re.compile(
        r"^\s*(?:(?:hôm nay|ngày mai)\s+)?(?:(?:tôi|em|mình)\s+)?"
        r"(?:nên\s+)?(?:ăn gì|ăn món gì|nấu món gì)[?.!\s]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:gợi ý|đề xuất|tư vấn)\s+(?:(?:giúp\s+)?(?:tôi|em|mình)\s+)?"
        r"(?:(?:một|vài)\s+)?(?:món ăn|quán ăn|nhà hàng|thực đơn)(?:\s+.*)?[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:(?:tôi|em|mình)\s+)?(?:muốn|đang)\s+(?:tìm|chọn)\s+"
        r"(?:món ăn|quán ăn|nhà hàng)(?:\s+.*)?[?.!]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:(?:hãy|giúp tôi|giúp mình)\s+)?(?:lập|lên|gợi ý|tạo)\s+"
        r"(?:(?:một|giúp\s+(?:tôi|mình)\s+(?:một\s+)?)?)?thực đơn(?:\s+.*)?[?.!]*$",
        re.IGNORECASE,
    ),
)
_DAILY_NONLEGAL_INTENTS_UNACCENTED = tuple(
    re.compile(strip_vietnamese_diacritics(pattern.pattern), re.IGNORECASE)
    for pattern in _DAILY_NONLEGAL_INTENTS
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
_SOCIAL_CHAT_INTENT = re.compile(
    r"\b(?:xin chào|chào bạn)\b.{0,60}\b(?:trò chuyện|nói chuyện|tán gẫu)\b",
    re.IGNORECASE,
)
_SOCIAL_NONLEGAL_SIGNAL_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_SOCIAL_NONLEGAL_SIGNAL.pattern), re.IGNORECASE
)
_GENERAL_KNOWLEDGE_SIGNAL = re.compile(
    r"^\s*(?:thủ đô\s+(?:của\s+)?[\w\s]+?\s+(?:là gì|là thành phố nào|ở đâu)|"
    r"thành phố nào\s+(?:là|được coi là)\s+thủ đô(?:\s+của\s+[\w\s]+)?)\s*[?!.]?\s*$",
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
    r"\b(?:và|đồng thời|ngoài ra|cùng với|kèm theo|bên cạnh đó)\b.{0,140}\b(?:"
    r"thuế(?:\s+chuyển nhượng|\s+thu nhập|\s+doanh nghiệp)?|hình sự|"
    r"hợp đồng lao động|doanh nghiệp|cổ phần|cổ đông|vốn góp|"
    r"tranh chấp đất(?: đai)?|ranh giới đất|hàng xóm lấn đất|"
    r"người tiêu dùng|bồi thường theo luật|chiếm đoạt|lừa đảo|"
    r"nồng độ cồn|xử phạt giao thông|tranh chấp thừa kế|phân chia di sản|di chúc)\b"
    r"|\b(?:tranh chấp đất(?: đai)?|ranh giới đất|hàng xóm lấn đất|"
    r"phân chia di sản|tranh chấp thừa kế|cổ phần doanh nghiệp|tranh chấp cổ phần|"
    r"thuế chuyển nhượng|chiếm đoạt tài sản|lừa đảo chiếm đoạt tài sản)\b",
    re.IGNORECASE,
)
_INDEPENDENT_OUTSIDE_TOPIC_UNACCENTED = re.compile(
    strip_vietnamese_diacritics(_INDEPENDENT_OUTSIDE_TOPIC.pattern), re.IGNORECASE
)


_GENERIC_LEGAL_DISPUTE_SIGNALS = (
    "quyền",
    "nghĩa vụ",
    "trách nhiệm",
    "căn cứ",
    "quy định",
    "văn bản",
    "biên bản",
    "quyết định",
    "thẩm quyền",
    "thời hiệu",
    "hiệu lực",
    "vô hiệu",
    "tranh chấp",
    "vi phạm",
    "xử lý",
    "bồi hoàn",
    "hoàn trả",
    "giấy triệu tập",
    "giấy phép",
    "chứng nhận",
    "bảo lãnh",
    "chữ ký số",
    "cam kết miệng",
    "điều khoản",
    "quy chế",
    "tiêu chí",
    "thu hồi",
    "cơ quan",
    "tòa án",
    "giải quyết",
    "lĩnh vực nào",
)
_NONLEGAL_ADMIN_PHRASES = re.compile(
    r"\b(?:hồ sơ xin việc|thủ tục nhập học|email xin nghỉ phép)\b",
    re.IGNORECASE,
)
_SPOUSE_PRISON_STATUS_MODIFIER = re.compile(
    r"\b(?:đang\s+)?(?:chấp hành án|thụ án)\s+phạt tù\b",
    re.IGNORECASE,
)
_CRIMINAL_SENTENCING_QUESTION = re.compile(
    r"\b(?:tội gì|khung hình phạt|truy cứu|phạm tội|hình sự|đi tù mấy năm|phạt bao nhiêu năm|bị phạt tù)\b",
    re.IGNORECASE,
)


def _has_generic_legal_dispute_signal(query: str, unaccented_query: str) -> bool:
    masked = _NONLEGAL_ADMIN_PHRASES.sub(" ", query)
    masked_unaccented = strip_vietnamese_diacritics(masked)
    return _has_any_term(masked, masked_unaccented, _GENERIC_LEGAL_DISPUTE_SIGNALS)


def _has_everyday_nonlegal_framing(query: str, unaccented_query: str) -> bool:
    everyday_cue = re.compile(
        r"\b(?:hướng dẫn|cách|gợi ý|giải thích|làm thế nào|vì sao|tại sao|"
        r"lập lịch|lên lịch|thiết kế|mới tập|bắt đầu làm)\b"
        r"|\b(?:nấu|chế biến|pha|chiên|xào|hấp|nướng|kho|luộc|vệ sinh|tập|chơi)\b"
        r".{0,40}\b(?:thế nào|như thế nào|ra sao|cần gì|ngon|trong|sạch)\b",
        re.IGNORECASE,
    )
    everyday_unaccented = re.compile(
        strip_vietnamese_diacritics(everyday_cue.pattern), re.IGNORECASE
    )
    return bool(everyday_cue.search(query) or everyday_unaccented.search(unaccented_query))


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
            or bool(_HNGD_DOMESTIC_VIOLENCE_PROTECTIVE_SIGNAL.search(query))
            or bool(_HNGD_DOMESTIC_VIOLENCE_PROTECTIVE_SIGNAL_UNACCENTED.search(unaccented_query))
            or _has_contextual_hngd_signal(query, unaccented_query)
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
        outside_match = (
            _has_any_term(query, unaccented_query, _OUT_OF_SCOPE_TERMS)
            or _has_out_of_scope_topic(query, unaccented_query)
        )
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
        explicit_inheritance_issue = _has_any_term(
            query, unaccented_query, ("thừa kế", "di sản", "người thừa kế", "phân chia di sản")
        )
        spouse_marital_property_issue = _has_any_term(
            query,
            unaccented_query,
            (
                "tài sản chung", "tài sản riêng", "chế độ tài sản",
                "tài sản của vợ chồng", "tài sản vợ chồng",
                "phần tài sản của vợ", "phần tài sản của chồng",
                "nhà đứng tên", "đất đứng tên", "có được ở tiếp",
                "quyền của người vợ", "quyền của người chồng",
            ),
        )
        if spouse_death_context and spouse_marital_property_issue:
            hngd_match = True
        if spouse_death_context and explicit_inheritance_issue:
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
            or _has_out_of_scope_topic(query, unaccented_query)
        )
        if (
            _CRIMINAL_SENTENCING_QUESTION.search(query)
            or _CRIMINAL_SENTENCING_QUESTION.search(unaccented_query)
        ):
            outside_match = True
        elif (
            _SPOUSE_PRISON_STATUS_MODIFIER.search(query)
            and hngd_match
            and not _has_out_of_scope_topic(query, unaccented_query)
        ):
            # In a family-law query, noting that a spouse is serving a prison
            # sentence is factual context (for example divorce procedure), not a
            # criminal-law question about offenses or sentencing.
            outside_match = False
        if (
            hngd_match
            and hngd_property_context
            and not independent_outside_topic
            and not (spouse_death_context and explicit_inheritance_issue)
        ):
            outside_match = False
        # A statement about studying law is not itself a request for legal help.
        education_statement = bool(
            _EDUCATION_STATEMENT.search(query)
            or _EDUCATION_STATEMENT_UNACCENTED.search(unaccented_query)
        )
        has_request = bool(_EXPLICIT_QUESTION_OR_REQUEST.search(query))
        generic_legal = _has_generic_legal_dispute_signal(query, unaccented_query)
        clear_nonlegal = (education_statement and not has_request) or any(
            signal.search(text)
            for signal, text in (
                (_CLEAR_NONLEGAL_SIGNAL, query),
                (_CLEAR_NONLEGAL_SIGNAL_UNACCENTED, unaccented_query),
                (_SOCIAL_NONLEGAL_SIGNAL, query),
                (_SOCIAL_CHAT_INTENT, query),
                # Greetings are checked only against the original text and
                # only as a complete utterance. Accent folding can turn
                # "chào bán" into "chao ban", colliding with "chào bạn".
                (_GENERAL_KNOWLEDGE_SIGNAL, query),
                (_GENERAL_KNOWLEDGE_SIGNAL_UNACCENTED, unaccented_query),
                (_GENERAL_ENTERTAINMENT_SIGNAL, query),
                (_GENERAL_ENTERTAINMENT_SIGNAL_UNACCENTED, unaccented_query),
                (_GENERAL_BANKING_SIGNAL, query),
                (_GENERAL_BANKING_SIGNAL_UNACCENTED, unaccented_query),
            )
        )
        clear_nonlegal = clear_nonlegal or any(
            pattern.search(text)
            for pattern, text in zip(
                _PRACTICAL_NONLEGAL_INTENTS + _PRACTICAL_NONLEGAL_INTENTS_UNACCENTED,
                (query,) * len(_PRACTICAL_NONLEGAL_INTENTS)
                + (unaccented_query,) * len(_PRACTICAL_NONLEGAL_INTENTS_UNACCENTED),
            )
        )
        clear_nonlegal = clear_nonlegal or any(
            pattern.search(text)
            for pattern, text in zip(
                _DAILY_NONLEGAL_INTENTS + _DAILY_NONLEGAL_INTENTS_UNACCENTED,
                (query,) * len(_DAILY_NONLEGAL_INTENTS)
                + (unaccented_query,) * len(_DAILY_NONLEGAL_INTENTS_UNACCENTED),
            )
        )
        # Step 1 (Safety precedence): Never let a clear non-legal / chat phrase
        # suppress a genuine legal question or out-of-scope legal query. Bare
        # incidental mentions inside non-legal prompts (for example, a poem
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
        # Step 2: Distinguish queries carrying legal/statutory/dispute intent
        # from everyday instructional/hobby questions with zero legal tokens.
        legal_intent = (
            hngd_match or outside_match or explicit_legal or generic_legal
        ) and not (education_statement and not has_request)

        if not legal_intent:
            if _has_everyday_nonlegal_framing(query, unaccented_query):
                return RouteDecision(
                    query_id=query_id,
                    route=Route.NON_LEGAL,
                    action=Action.GENERAL_CHAT,
                    route_reason=RouteReason.NON_LEGAL_NO_LEGAL_INTENT,
                    as_of_date=as_of_date,
                )
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

