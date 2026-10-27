"""Unit tests for reranking/reranker.py (Dev 5), mock-first: no model or index needed."""
import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reranking.reranker import (  # noqa: E402
    CrossEncoderScorer,
    MockScorer,
    Reranker,
    RerankerConfig,
    build_reranker,
    deduplicate_candidates,
    load_reranker_config,
)

FIXTURE = json.loads((ROOT / "test" / "fixtures" / "reranker_candidates.json").read_text(encoding="utf-8"))
QUERY = FIXTURE["query"]


def candidates():
    """The five unique fixture candidates (the trailing duplicate excluded)."""
    return copy.deepcopy(FIXTURE["candidates"][:5])


def fixture_reranker(**kwargs):
    return Reranker(MockScorer(FIXTURE["mock_scores"]), **kwargs)


class RecordingScorer:
    def __init__(self, scores=None):
        self.scores = scores
        self.calls = []

    def score(self, query, hits):
        self.calls.append((query, [hit["chunk_id"] for hit in hits]))
        return self.scores if self.scores is not None else [float(-i) for i in range(len(hits))]


class RerankerConfigTest(unittest.TestCase):
    def write_config(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def test_repository_config_has_documented_defaults(self):
        config = load_reranker_config()
        self.assertEqual(config, RerankerConfig(
            enabled=True, backend="cross_encoder", model="BAAI/bge-reranker-v2-m3",
            rerank_top_k=5, max_candidates=50, batch_size=16, max_length=512, device=None, dtype="auto"))

    def test_overrides_win_and_none_overrides_are_ignored(self):
        config = load_reranker_config(rerank_top_k=3, max_candidates=20, backend=None)
        self.assertEqual((config.rerank_top_k, config.max_candidates, config.backend), (3, 20, "cross_encoder"))

    def test_unknown_keys_are_rejected_to_catch_typos(self):
        path = self.write_config("reranker:\n  rerank_topk: 5\n")
        with self.assertRaisesRegex(ValueError, "rerank_topk"):
            load_reranker_config(path)

    def test_missing_section_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "thiếu mục 'reranker'"):
            load_reranker_config(self.write_config("retrieval:\n  retrieval_top_k: 50\n"))

    def test_invalid_values_are_rejected(self):
        cases = [
            ({"rerank_top_k": 0}, "rerank_top_k"),
            ({"rerank_top_k": True}, "rerank_top_k"),
            ({"max_candidates": 2.5}, "max_candidates"),
            ({"rerank_top_k": 10, "max_candidates": 5}, "không được lớn hơn max_candidates"),
            ({"backend": "colbert"}, "backend"),
            ({"enabled": "yes"}, "enabled"),
        ]
        for values, message in cases:
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, message):
                RerankerConfig(**values)


class RerankerTest(unittest.TestCase):
    def test_reorders_by_reranker_score_and_assigns_ranks_from_one(self):
        results = fixture_reranker().rerank(QUERY, candidates(), top_k=3)
        self.assertEqual([row["chunk_id"] for row in results], [
            "l_52_2014_qh13_art_8_chunk_1", "l_22_2000_qh10_art_9_chunk_1", "l_52_2014_qh13_art_8_chunk_2"])
        self.assertEqual([row["rank"] for row in results], [1, 2, 3])
        self.assertEqual([row["score"] for row in results], [0.97, 0.81, 0.55])

    def test_keeps_every_input_field_and_only_updates_rank_and_score(self):
        inputs = candidates()
        original = copy.deepcopy(inputs)
        results = fixture_reranker().rerank(QUERY, inputs, top_k=5)
        by_id = {row["chunk_id"]: row for row in original}
        for row in results:
            source = by_id[row["chunk_id"]]
            for key, value in source.items():
                if key not in ("rank", "score"):
                    self.assertEqual(row[key], value, key)
            self.assertEqual(row["retrieval_rank"], source["rank"])
            self.assertEqual(row["retrieval_score"], source["rrf_score"])
        top = results[0]
        self.assertEqual(top["parent_clause_id"], "l_52_2014_qh13_art_8_clause_1")
        self.assertEqual(top["document_id"], "l_52_2014_qh13")
        self.assertEqual(top["metadata"]["validity_status"], "Không xác định")
        self.assertEqual(inputs, original, "input candidates must not be mutated")

    def test_default_top_k_comes_from_rerank_top_k(self):
        self.assertEqual(len(fixture_reranker(rerank_top_k=2).rerank(QUERY, candidates())), 2)

    def test_invalid_top_k_and_query_are_rejected(self):
        reranker = fixture_reranker()
        for top_k in (0, -1, True, 1.5):
            with self.subTest(top_k=top_k), self.assertRaisesRegex(ValueError, "top_k"):
                reranker.rerank(QUERY, candidates(), top_k=top_k)
        for query in ("", "   ", None):
            with self.subTest(query=query), self.assertRaisesRegex(ValueError, "query"):
                reranker.rerank(query, candidates())

    def test_caps_candidates_sent_to_scorer_at_max_candidates(self):
        scorer = RecordingScorer()
        reranker = Reranker(scorer, rerank_top_k=2, max_candidates=3)
        results = reranker.rerank(QUERY, candidates())
        self.assertEqual(scorer.calls[0][1], [row["chunk_id"] for row in candidates()[:3]])
        self.assertEqual(len(results), 2)
        self.assertEqual(reranker.last_stats["input_candidates"], 5)
        self.assertEqual(reranker.last_stats["truncated_candidates"], 2)
        self.assertEqual(reranker.last_stats["scored_candidates"], 3)

    def test_empty_candidates_return_empty_list_without_scoring(self):
        scorer = RecordingScorer()
        reranker = Reranker(scorer)
        self.assertEqual(reranker.rerank(QUERY, []), [])
        self.assertEqual(reranker.rerank(QUERY, None), [])
        self.assertEqual(scorer.calls, [])
        self.assertEqual(reranker.last_stats["output_candidates"], 0)

    def test_duplicate_chunk_ids_are_scored_once_and_keep_first_occurrence(self):
        scorer = RecordingScorer()
        reranker = Reranker(scorer)
        results = reranker.rerank(QUERY, copy.deepcopy(FIXTURE["candidates"]), top_k=10)
        ids = [row["chunk_id"] for row in results]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(scorer.calls[0][1].count("l_52_2014_qh13_art_8_chunk_2"), 1)
        kept = next(row for row in results if row["chunk_id"] == "l_52_2014_qh13_art_8_chunk_2")
        self.assertEqual(kept["retrieval_rank"], 3)
        self.assertEqual(reranker.last_stats["duplicates_removed"], 1)

    def test_deduplication_fills_missing_fields_from_later_copies(self):
        rows, duplicates = deduplicate_candidates([
            {"chunk_id": "A", "chunk_text": "a", "metadata": {}},
            {"chunk_id": "A", "chunk_text": "other", "document_id": "doc", "metadata": {"validity_status": "Còn hiệu lực"}},
        ])
        self.assertEqual(duplicates, 1)
        self.assertEqual(rows, [{"chunk_id": "A", "chunk_text": "a", "document_id": "doc",
                                 "metadata": {"validity_status": "Còn hiệu lực"}}])

    def test_candidate_without_chunk_id_is_rejected(self):
        for bad in ({"chunk_text": "x"}, {"chunk_id": "", "chunk_text": "x"}, {"chunk_id": 5}, "not-a-dict"):
            with self.subTest(candidate=bad), self.assertRaises(ValueError):
                fixture_reranker().rerank(QUERY, [bad])

    def test_scorer_output_is_validated(self):
        with self.assertRaisesRegex(ValueError, "1 điểm cho 2 candidate"):
            Reranker(RecordingScorer([1.0])).rerank(QUERY, candidates()[:2])
        with self.assertRaisesRegex(ValueError, "không hợp lệ"):
            Reranker(RecordingScorer([math.nan, 1.0])).rerank(QUERY, candidates()[:2])

    def test_ties_keep_retrieval_order(self):
        results = Reranker(MockScorer({}, default=0.5)).rerank(QUERY, candidates(), top_k=5)
        self.assertEqual([row["chunk_id"] for row in results], [row["chunk_id"] for row in candidates()])

    def test_logs_candidate_counts_and_latency(self):
        with self.assertLogs("reranking.reranker", level="INFO") as logs:
            fixture_reranker(rerank_top_k=2, max_candidates=4).rerank(QUERY, candidates())
        self.assertRegex(logs.output[0], r"input=5 scored=4 .* output=2 latency=\d+\.\dms")


class ScorerTest(unittest.TestCase):
    def test_mock_scorer_uses_fixed_scores_with_default(self):
        scores = MockScorer({"A": 0.7}, default=-1.0).score("q", [{"chunk_id": "A"}, {"chunk_id": "B"}])
        self.assertEqual(scores, [0.7, -1.0])

    def test_mock_scorer_lexical_overlap_handles_word_segmented_text(self):
        hits = [
            {"chunk_id": "A", "chunk_text": "Điều_kiện kết_hôn của nam và nữ"},
            {"chunk_id": "B", "text": "Chia tài sản khi ly hôn"},
            {"chunk_id": "C", "chunk_text": ""},
        ]
        # Share of the 4 distinct query tokens found in each text; B only shares "hôn".
        self.assertEqual(MockScorer().score("điều kiện kết hôn", hits), [1.0, 0.25, 0.0])

    def test_cross_encoder_scores_query_chunk_text_pairs(self):
        class FakeModel:
            def predict(self, pairs, batch_size, show_progress_bar):
                self.pairs, self.batch_size = pairs, batch_size
                return [0.25 for _ in pairs]

        model = FakeModel()
        scorer = CrossEncoderScorer(batch_size=4, model=model)
        scores = scorer.score("câu hỏi", [{"chunk_id": "A", "chunk_text": "nội dung A"},
                                          {"chunk_id": "B", "text": "nội dung B"}])
        self.assertEqual(scores, [0.25, 0.25])
        self.assertEqual(model.pairs, [("câu hỏi", "nội dung A"), ("câu hỏi", "nội dung B")])
        self.assertEqual(model.batch_size, 4)

    def test_model_load_time_is_reported_separately_from_rerank_latency(self):
        class SlowLoadingScorer(MockScorer):
            loads = 0

            def load(self):
                SlowLoadingScorer.loads += 1

        reranker = Reranker(SlowLoadingScorer({}))
        reranker.rerank(QUERY, [])
        self.assertEqual(SlowLoadingScorer.loads, 0, "no model load for empty candidates")
        reranker.rerank(QUERY, candidates())
        self.assertEqual(SlowLoadingScorer.loads, 1)
        self.assertIn("model_load_ms", reranker.last_stats)

    def test_cross_encoder_loads_lazily_and_reports_missing_dependency(self):
        scorer = CrossEncoderScorer()
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            with self.assertRaisesRegex(RuntimeError, "sentence-transformers"):
                scorer.score("q", [{"chunk_id": "A", "chunk_text": "x"}])


class BuildRerankerTest(unittest.TestCase):
    def test_disabled_config_returns_none(self):
        self.assertIsNone(build_reranker(RerankerConfig(enabled=False)))

    def test_mock_backend(self):
        reranker = build_reranker(RerankerConfig(rerank_top_k=3, max_candidates=10))
        self.assertIsInstance(reranker.scorer, MockScorer)
        self.assertEqual(reranker.describe(), {"backend": "mock", "model": None,
                                               "rerank_top_k": 3, "max_candidates": 10,
                                               "candidate_text": "chunk_text"})

    def test_cross_encoder_backend_does_not_load_model_eagerly(self):
        reranker = build_reranker(RerankerConfig(backend="cross_encoder", batch_size=8, max_length=256))
        self.assertIsInstance(reranker.scorer, CrossEncoderScorer)
        self.assertIsNone(reranker.scorer._model)
        self.assertEqual((reranker.scorer.batch_size, reranker.scorer.max_length), (8, 256))
        self.assertEqual(reranker.describe()["model"], "BAAI/bge-reranker-v2-m3")
        self.assertEqual(reranker.describe()["dtype"], "auto")


class CrossEncoderDtypeTest(unittest.TestCase):
    def test_auto_dtype_is_float16_on_cuda_and_float32_on_cpu(self):
        scorer = CrossEncoderScorer()
        self.assertEqual(scorer.resolve_dtype(None, True), "float16")
        self.assertEqual(scorer.resolve_dtype(None, False), "float32")
        self.assertEqual(scorer.resolve_dtype("cuda:0", False), "float16")
        self.assertEqual(scorer.resolve_dtype("cpu", True), "float32")
        self.assertEqual(CrossEncoderScorer(dtype="bfloat16").resolve_dtype("cpu", False), "bfloat16")

    def test_invalid_dtype_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "dtype"):
            RerankerConfig(dtype="int8")
        with self.assertRaisesRegex(ValueError, "dtype"):
            CrossEncoderScorer(dtype="half")

    def test_model_is_loaded_with_the_resolved_dtype(self):
        loaded = {}

        class FakeCrossEncoder:
            def __init__(self, name, **kwargs):
                loaded.update(name=name, **kwargs)

        fake_torch = mock.Mock(float16="torch.float16", float32="torch.float32")
        fake_torch.cuda.is_available.return_value = True
        fake_st = mock.Mock(CrossEncoder=FakeCrossEncoder)
        with mock.patch.dict(sys.modules, {"torch": fake_torch, "sentence_transformers": fake_st}):
            CrossEncoderScorer(max_length=256).load()
        self.assertEqual(loaded, {"name": "BAAI/bge-reranker-v2-m3", "max_length": 256, "device": None,
                                  "model_kwargs": {"torch_dtype": "torch.float16"}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
