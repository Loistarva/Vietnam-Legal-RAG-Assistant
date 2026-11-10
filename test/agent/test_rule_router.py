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

    def test_r4_additional_marriage_and_parentage_queries_are_hngd(self):
        queries = (
            "Bao nhiêu tuổi thì được cưới?",
            "Xác định cha cho đứa bé sinh ngoài giá thú thế nào?",
            "Tảo hôn bị xử lý ra sao?",
            "Bố mẹ ly thân thì con 10 tuổi ở với ai?",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.LEGAL_HNGD)
                self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)

    def test_everyday_wedding_mention_does_not_match_hngd_context(self):
        decision = self.router.route("Tôi đi dự đám cưới bạn.")
        self.assertNotEqual(decision.route, Route.LEGAL_HNGD)

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
            "Viết một bài thơ về ly hôn",
            "Viết email xin nghỉ phép dù vợ tôi đang ly thân",
            "Tôi đang học môn Luật HNGĐ",
        )
        for query in cases:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.NON_LEGAL)
                self.assertEqual(decision.action, Action.GENERAL_CHAT)
                self.assertEqual(decision.route_reason, RouteReason.NON_LEGAL_NO_LEGAL_INTENT)

    def test_mixed_general_and_legal_requests_take_safe_abstention_route(self):
        queries = (
            "Viết email xin nghỉ phép, đồng thời hỏi công ty nợ lương xử lý thế nào theo quy định?",
            "Tôi cần hồ sơ xin việc, nhưng công ty giữ lương trái pháp luật thì khiếu nại ở đâu?",
            "Gợi ý quà sinh nhật cho mẹ; hỏi thêm mẹ kế có được hưởng thừa kế không?",
            "Tôi muốn học Python, đồng thời hỏi vợ chồng có quyền chia tài sản chung thế nào?",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.MIXED_LEGAL_SCOPE)
                self.assertEqual(decision.action, Action.POLICY_ABSTENTION)
                self.assertEqual(decision.route_reason, RouteReason.MIXED_LEGAL_SCOPE)

    def test_r4_mixed_legal_request_is_never_overridden_by_nonlegal_signal(self):
        queries = (
            "Viết email xin nghỉ phép, đồng thời hỏi công ty nợ lương xử lý thế nào theo quy định?",
            "Tôi cần hồ sơ xin việc, nhưng công ty giữ lương trái pháp luật thì khiếu nại ở đâu?",
            "Gợi ý quà sinh nhật cho mẹ; hỏi thêm mẹ kế có được hưởng thừa kế không?",
            "Tôi muốn học Python, đồng thời hỏi vợ chồng có quyền chia tài sản chung thế nào?",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertNotEqual(decision.action, Action.GENERAL_CHAT)
                self.assertEqual(decision.route, Route.MIXED_LEGAL_SCOPE)
                self.assertEqual(decision.action, Action.POLICY_ABSTENTION)

    def test_r4_criminal_and_civil_out_of_scope_queries_abstain(self):
        queries = (
            "Trộm cắp tài sản 5 triệu đi tù mấy năm?",
            "Phạm tội cố ý gây thương tích bị phạt bao nhiêu năm?",
            "Thuê nhà mà chủ nhà không trả tiền cọc thì làm sao?",
            "Tôi bị lừa chuyển khoản 50 triệu, có lấy lại được không?",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.LEGAL_OUT_OF_SCOPE)
                self.assertEqual(decision.action, Action.POLICY_ABSTENTION)

    def test_r4_hngd_support_queries_with_labor_capacity_are_not_mixed(self):
        queries = (
            "Con da thanh nien nhung mat kha nang lao dong va khong co tai san tu nuoi song co the yeu cau cha me tiep tuc cap duong khong?",
            "Người con có phải thực hiện nghĩa vụ cấp dưỡng cho cha mẹ đã cao tuổi và không còn khả năng lao động trong trường hợp nào?",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.LEGAL_HNGD)
                self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)

    def test_r4_consumer_warranty_dispute_is_out_of_scope(self):
        decision = self.router.route(
            "Người mua xe điện phát hiện lỗi pin lặp lại nhưng nhà phân phối từ chối bảo hành, cơ quan nào có thể giải quyết tranh chấp?"
        )
        self.assertEqual(decision.route, Route.LEGAL_OUT_OF_SCOPE)
        self.assertEqual(decision.action, Action.POLICY_ABSTENTION)

    def test_r4_ordinary_bank_transfer_is_nonlegal_not_out_of_scope(self):
        decision = self.router.route("Hướng dẫn chuyển khoản ngân hàng như thế nào?")
        self.assertEqual(decision.route, Route.NON_LEGAL)
        self.assertEqual(decision.action, Action.GENERAL_CHAT)

    def test_r4_social_general_knowledge_and_entertainment_are_nonlegal(self):
        queries = (
            "Cảm ơn bạn nhé!",
            "Chào buổi sáng.",
            "Thủ đô của Úc là gì?",
            "Kể chuyện cười đi.",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.NON_LEGAL)
                self.assertEqual(decision.action, Action.GENERAL_CHAT)

    def test_r4_social_phrase_inside_legal_query_does_not_override_intent(self):
        decision = self.router.route(
            "Cảm ơn bạn, nhưng vợ chồng có quyền chia tài sản thế nào?"
        )
        self.assertNotEqual(decision.action, Action.GENERAL_CHAT)

    def test_creative_request_about_divorce_remains_nonlegal(self):
        decision = self.router.route("Viết một bài thơ về ly hôn")
        self.assertEqual(decision.route, Route.NON_LEGAL)
        self.assertEqual(decision.action, Action.GENERAL_CHAT)

    def test_classifier_version_is_incremented_for_router_precedence_change(self):
        decision = self.router.route("Chào bạn")
        self.assertEqual(decision.classifier_version, "rule_router_v3")

    def test_generic_legal_request_enters_retrieval_for_confidence_gate(self):
        decision = self.router.route("Tôi cần tư vấn pháp luật")
        self.assertEqual(decision.route, Route.LEGAL_SCOPE_UNCERTAIN)
        self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)
        self.assertEqual(decision.route_reason, RouteReason.LEGAL_SCOPE_UNCERTAIN)

    def test_unrecognized_question_defaults_to_safe_retrieval(self):
        decision = self.router.route("Quy định trong trường hợp đặc biệt này thế nào?")
        self.assertEqual(decision.route, Route.LEGAL_SCOPE_UNCERTAIN)
        self.assertEqual(decision.action, Action.LEGAL_RETRIEVAL)

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

    def test_r4_spouse_death_and_property_is_mixed_but_marital_inheritance_stays_hngd(self):
        decision = self.router.route(
            "Chồng mất, nhà đứng tên chồng thì vợ có được ở tiếp không?"
        )
        self.assertEqual(decision.route, Route.MIXED_LEGAL_SCOPE)
        self.assertEqual(decision.action, Action.POLICY_ABSTENTION)

        control = self.router.route(
            "Tài sản thừa kế trong thời kỳ hôn nhân có phải tài sản chung không?"
        )
        self.assertEqual(control.route, Route.LEGAL_HNGD)
        self.assertEqual(control.action, Action.LEGAL_RETRIEVAL)

    def test_generic_employment_and_admission_paperwork_stays_nonlegal(self):
        for query in (
            "Tôi cần hồ sơ xin việc gồm những gì?",
            "Hướng dẫn thủ tục nhập học đại học",
        ):
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertEqual(decision.route, Route.NON_LEGAL)
                self.assertEqual(decision.action, Action.GENERAL_CHAT)

    def test_nonlegal_study_schedule_stays_general_chat(self):
        decision = self.router.route(
            "Giúp tôi lập lịch học Python trong hai tuần, mỗi ngày khoảng ba mươi phút."
        )
        self.assertEqual(decision.route, Route.NON_LEGAL)
        self.assertEqual(decision.action, Action.GENERAL_CHAT)

    def test_negated_family_scope_does_not_override_independent_land_dispute(self):
        decision = self.router.route(
            "Hai hộ liền kề tranh chấp mốc ranh giới thửa đất thì phải thực hiện "
            "thủ tục giải quyết nào? Không có tranh chấp tài sản vợ chồng."
        )
        self.assertEqual(decision.route, Route.LEGAL_OUT_OF_SCOPE)
        self.assertEqual(decision.action, Action.POLICY_ABSTENTION)

    def test_review_holdout_family_questions_never_go_to_general_chat(self):
        queries = (
            "Chồng tôi ngoại tình, tôi muốn đơn phương ly dị thì làm sao?",
            "Vợ tôi bỏ đi 3 năm không liên lạc, tôi có thể ly dị được không?",
            "Tuổi tối thiểu để lấy vợ là bao nhiêu?",
            "Hai người đồng giới có được cưới nhau không?",
            "Bố mẹ ly thân thì con 10 tuổi ở với ai?",
            "Tiền lương của chồng có phải là của chung không?",
            "Anh em họ trong phạm vi ba đời có được lấy nhau không?",
            "ly hon thi chia tai san the nao",
            "Lao động của vợ trong gia đình có được coi như lao động có thu nhập khi chia tài sản chung không?",
            "Vốn góp vào doanh nghiệp bằng tài sản chung của vợ chồng có cần chồng đồng ý không?",
            "Tài sản chung là quyền sử dụng đất thì khi chia phải làm sao?",
            "Con nuôi có được hưởng thừa kế như con đẻ không?",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertNotEqual(decision.action, Action.GENERAL_CHAT)
                self.assertEqual(decision.route, Route.LEGAL_HNGD)

    def test_review_holdout_out_of_scope_legal_questions_do_not_go_to_chat(self):
        queries = (
            "Công ty nợ lương 3 tháng thì tôi làm gì?",
            "Hàng xóm xây nhà lấn sang đất nhà tôi thì kiện ở đâu?",
            "Cho vay tiền không có giấy tờ có đòi được không?",
            "Mua hàng online bị lừa thì báo công an thế nào?",
        )
        for query in queries:
            with self.subTest(query=query):
                decision = self.router.route(query)
                self.assertNotEqual(decision.action, Action.GENERAL_CHAT)
                self.assertEqual(decision.route, Route.LEGAL_OUT_OF_SCOPE)

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
