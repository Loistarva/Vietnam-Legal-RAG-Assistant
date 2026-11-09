"""Routing decisions, fast-path precedence, and safety invariants."""
from __future__ import annotations

import logging
import unittest
from datetime import date
from io import StringIO

from agent.router.rule_router import (
    Action,
    FastPathRule,
    Route,
    RouteReason,
    RouterInputError,
    RuleRouter,
)


class RuleRouterTest(unittest.TestCase):
    def setUp(self):
        self.router = RuleRouter()

    def test_hngd_question_routes_to_legal_retrieval(self):
        decision = self.router.route(
            "Điều kiện kết hôn theo Luật HNGĐ 2014 là gì?", query_id="HN_001"
        )
        self.assertEqual(decision.route, Route.LEGAL_HNGD)
        self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)
        self.assertEqual(decision.route_reason, RouteReason.HNGD_DOMAIN_MATCH)

    def test_child_custody_after_divorce_is_hngd(self):
        decision = self.router.route("Sau ly hôn ai có quyền nuôi con?")
        self.assertEqual(decision.route, Route.LEGAL_HNGD)

    def test_spousal_property_is_hngd(self):
        decision = self.router.route("Chế độ tài sản của vợ chồng là gì?")
        self.assertEqual(decision.route, Route.LEGAL_HNGD)

    def test_child_support_is_hngd(self):
        decision = self.router.route("Nghĩa vụ cấp dưỡng sau ly hôn")
        self.assertEqual(decision.route, Route.LEGAL_HNGD)

    def test_hngd_topic_routes_without_question_marker(self):
        for query in (
            "Cấp dưỡng có thể thực hiện một lần thay vì hằng tháng không?",
            "Chồng có quyền tự yêu cầu ly hôn khi vợ đang mang thai không?",
            "Phạm vi điều chỉnh của Luật Hôn nhân và gia đình 2014",
            "Tôi muốn kết hôn với người nước ngoài. Tôi phải nộp hồ sơ ở đâu?",
            "Thời kỳ hôn nhân và tài sản riêng",
            "Quyền thăm nom con sau ly hôn",
        ):
            with self.subTest(query=query):
                self.assertEqual(self.router.route(query).action, Action.LEGAL_RETRIEVAL)

    def test_legal_out_of_scope_routes_to_abstention_without_marker(self):
        for query in (
            "Di chúc và di sản",
            "Ranh giới thửa đất",
            "Doanh nghiệp và lao động",
            "Vượt đèn đỏ",
        ):
            with self.subTest(query=query):
                self.assertEqual(self.router.route(query).route, Route.LEGAL_OUT_OF_SCOPE)
                self.assertEqual(self.router.route(query).action, Action.POLICY_ABSTENTION)

    def test_parentage_question_is_hngd(self):
        decision = self.router.route("Xác định cha, mẹ, con theo pháp luật")
        self.assertEqual(decision.route, Route.LEGAL_HNGD)

    def test_other_legal_domain_abstains(self):
        cases = (
            "Điều kiện cấp sổ đỏ là gì?",
            "Thuế thu nhập cá nhân được tính thế nào?",
            "Tội trộm cắp bị xử lý thế nào?",
            "Quy định về hợp đồng lao động",
            "Vi phạm giao thông bị xử phạt ra sao?",
        )
        for query in cases:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.LEGAL_OUT_OF_SCOPE)
                self.assertEqual(decision.action, Action.POLICY_ABSTENTION)
                self.assertEqual(decision.route_reason, RouteReason.LEGAL_OUT_OF_SCOPE_MATCH)

    def test_review_examples_route_to_expected_legal_scope(self):
        cases = (
            ("Kết hôn với người nước ngoài cần giấy tờ gì?", Route.LEGAL_HNGD),
            ("Luật thuế mới nhất quy định gì?", Route.LEGAL_OUT_OF_SCOPE),
            ("Tôi bị công ty sa thải, có đúng luật không?", Route.LEGAL_OUT_OF_SCOPE),
            ("Tư vấn hợp đồng mua bán nhà đất", Route.LEGAL_OUT_OF_SCOPE),
            (
                "Hôm nay tôi bị phạt vì đỗ xe sai quy định",
                Route.LEGAL_OUT_OF_SCOPE,
            ),
        )
        for query, expected_route in cases:
            with self.subTest(query=query):
                self.assertEqual(self.router.route(query).route, expected_route)

    def test_nonlegal_examples_go_to_general_chat(self):
        cases = (
            "Xin chào, bạn khỏe không?",
            "Viết giúp tôi một email xin nghỉ phép",
            "Giải thích thuật toán Binary Search",
            "Viết một bài thơ về tình yêu",
            "Hướng dẫn học Python cơ bản",
            "Viết lời chúc cho vợ nhân ngày sinh nhật",
            "Tôi đang học môn Luật HNGĐ",
        )
        for query in cases:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.NON_LEGAL)
                self.assertEqual(decision.action, Action.GENERAL_CHAT)
                self.assertEqual(decision.route_reason, RouteReason.NON_LEGAL_NO_LEGAL_INTENT)

    def test_generic_legal_request_enters_retrieval_for_confidence_gate(self):
        decision = self.router.route("Tôi cần tư vấn pháp luật")
        self.assertEqual(decision.route, Route.LEGAL_SCOPE_UNCERTAIN)
        self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)
        self.assertEqual(decision.route_reason, RouteReason.LEGAL_SCOPE_UNCERTAIN)

    def test_unknown_cited_legal_scope_enters_retrieval(self):
        decision = self.router.route("Khoản 2 Điều 5 quy định thế nào?")
        self.assertEqual(decision.route, Route.LEGAL_SCOPE_UNCERTAIN)
        self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)

    def test_unspecified_legal_rights_enter_retrieval_for_confidence_gate(self):
        for query in (
            "Tôi có quyền yêu cầu bồi thường không?",
            "Tôi có quyền khởi kiện không?",
        ):
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.LEGAL_SCOPE_UNCERTAIN)
                self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)

    def test_mixed_scope_is_not_routed_as_hngd_only(self):
        for query in (
            "Chia tài sản khi ly hôn và nghĩa vụ thuế liên quan",
            "Ly hôn, chia tài sản và tranh chấp đất đai thì giải quyết thế nào?",
            "Ly hôn chia tài sản và phân chia di sản theo thừa kế thì sao?",
        ):
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.MIXED_LEGAL_SCOPE)
                self.assertEqual(decision.action, Action.POLICY_ABSTENTION)
                self.assertEqual(decision.route_reason, RouteReason.MIXED_LEGAL_SCOPE)

    def test_land_or_inheritance_as_marital_property_stays_hngd(self):
        for query in (
            "Ly hôn, chia tài sản và quyền sử dụng đất được giải quyết thế nào?",
            "Tài sản thừa kế trong thời kỳ hôn nhân có phải tài sản chung không?",
        ):
            with self.subTest(query=query):
                self.assertEqual(self.router.route(query).route, Route.LEGAL_HNGD)

    def test_generic_employment_and_admission_paperwork_stays_nonlegal(self):
        for query in (
            "Tôi cần hồ sơ xin việc gồm những gì?",
            "Hướng dẫn thủ tục nhập học đại học",
        ):
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.NON_LEGAL)
                self.assertEqual(decision.action, Action.GENERAL_CHAT)

    def test_whitespace_and_case_normalization(self):
        decision = self.router.route("  ĐIỀU KIỆN   KẾT HÔN LÀ GÌ? ")
        self.assertEqual(decision.route, Route.LEGAL_HNGD)

    def test_does_not_match_generic_family_words_as_legal(self):
        decision = self.router.route("Tôi muốn mua quà sinh nhật cho vợ")
        self.assertEqual(decision.route, Route.NON_LEGAL)

    def test_as_of_date_is_preserved_exactly(self):
        original_date = "2014-06-01"
        decision = self.router.route(
            "Theo Luật HNGĐ, điều kiện kết hôn là gì?",
            query_id="HN_010",
            as_of_date=original_date,
        )
        self.assertEqual(decision.as_of_date, original_date)
        self.assertEqual(decision.to_dict()["as_of_date"], original_date)

    def test_date_object_is_preserved_and_serializes_as_iso(self):
        value = date(2014, 6, 1)
        decision = self.router.route("Điều kiện kết hôn là gì?", as_of_date=value)
        self.assertIs(decision.as_of_date, value)
        self.assertEqual(decision.to_dict()["as_of_date"], "2014-06-01")

    def test_empty_or_non_string_query_is_validation_error(self):
        for query in ("", "   ", None, 42):
            with self.subTest(query=query):
                with self.assertRaises(RouterInputError) as context:
                    self.router.route(query)
                expected_reason = (
                    RouteReason.INVALID_EMPTY_QUERY
                    if isinstance(query, str)
                    else RouteReason.INVALID_QUERY_TYPE
                )
                self.assertEqual(context.exception.reason_code, expected_reason)

    def test_invalid_as_of_date_is_rejected_not_replaced(self):
        with self.assertRaises(RouterInputError):
            self.router.route("Điều kiện kết hôn là gì?", as_of_date="08/11/2026")

    def test_every_successful_decision_has_reason_and_is_deterministic(self):
        query = "Sau ly hôn ai có quyền nuôi con?"
        first = self.router.route(query, as_of_date="2020-01-01")
        second = self.router.route(query, as_of_date="2020-01-01")
        self.assertTrue(first.route_reason.value)
        self.assertEqual(first, second)

    def test_route_log_has_decision_fields_but_not_raw_query(self):
        stream = StringIO()
        logger = logging.getLogger("test.rule_router.safe_log")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler(stream))
        router = RuleRouter(logger=logger)
        query = "Tôi cần tư vấn pháp luật: thông tin riêng tư xyz"
        router.route(query, query_id="HN_999")
        output = stream.getvalue()
        self.assertIn('"event":"route_decision"', output)
        self.assertIn('"query_id":"HN_999"', output)
        self.assertIn('"route_reason":"LEGAL_SCOPE_UNCERTAIN"', output)
        self.assertNotIn("thông tin riêng tư xyz", output)


class FastPathTest(unittest.TestCase):
    def approved_rule(self, **overrides):
        values = {
            "rule_id": "FP_HNGD_001",
            "patterns": ("điều kiện kết hôn là gì?",),
            "response_key": "verified.marriage_age",
            "citation_refs": ("L52_2014_QH13_ART_8",),
            "approved": True,
        }
        values.update(overrides)
        return FastPathRule(**values)

    def test_exact_approved_whitelist_rule_fast_paths_before_classifier(self):
        router = RuleRouter([self.approved_rule()])
        # If ordinary classification ran first, this forced assertion would fail the test.

        def fail_classifier(*args, **kwargs):
            self.fail("fast-path must run before ordinary classification")

        router._classify_normalized_query = fail_classifier
        decision = router.route("  ĐIỀU KIỆN KẾT HÔN LÀ GÌ? ", query_id="HN_001")
        self.assertEqual(decision.route, Route.LEGAL_HNGD)
        self.assertEqual(decision.action, Action.FAST_PATH)
        self.assertEqual(decision.route_reason, RouteReason.FAST_PATH_RULE_MATCH)
        self.assertEqual(decision.matched_rule_id, "FP_HNGD_001")
        self.assertTrue(decision.fast_path)

    def test_near_match_or_extra_request_does_not_fast_path(self):
        router = RuleRouter([self.approved_rule()])
        for query in (
            "Điều kiện kết hôn là gì",
            "Điều kiện kết hôn là gì? Và kết hôn với người nước ngoài thì sao?",
        ):
            with self.subTest(query=query):
                self.assertFalse(router.route(query).fast_path)

    def test_unapproved_or_unhandled_rule_falls_through_to_retrieval(self):
        rule = self.approved_rule(approved=False)
        decision = RuleRouter([rule]).route("Điều kiện kết hôn là gì?")
        self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)
        self.assertFalse(decision.fast_path)

        no_handler = self.approved_rule(response_key=None)
        decision = RuleRouter([no_handler]).route("Điều kiện kết hôn là gì?")
        self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)
        self.assertFalse(decision.fast_path)

    def test_effective_period_uses_query_date_and_exclusive_end(self):
        rule = self.approved_rule(effective_from="2020-01-01", effective_to="2021-01-01")
        router = RuleRouter([rule])
        self.assertFalse(router.route("Điều kiện kết hôn là gì?").fast_path)
        self.assertTrue(router.route("Điều kiện kết hôn là gì?", as_of_date="2020-01-01").fast_path)
        self.assertFalse(router.route("Điều kiện kết hôn là gì?", as_of_date="2021-01-01").fast_path)

    def test_duplicate_rule_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duy nhất"):
            RuleRouter([self.approved_rule(), self.approved_rule()])

    def test_duplicate_normalized_patterns_are_rejected(self):
        first = self.approved_rule(rule_id="FP_ONE")
        second = self.approved_rule(
            rule_id="FP_TWO", patterns=("  ĐIỀU KIỆN   KẾT HÔN LÀ GÌ?  ",)
        )
        with self.assertRaisesRegex(ValueError, "pattern bị trùng"):
            RuleRouter([first, second])


if __name__ == "__main__":
    unittest.main()
