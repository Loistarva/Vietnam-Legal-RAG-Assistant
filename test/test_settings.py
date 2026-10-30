import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from retrieval.settings import load_settings, validate_settings
from scripts.build_index import resolve_build_config
from retrieval.retrieval_evaluation import evaluate


class RetrievalSettingsTest(unittest.TestCase):
    def test_loads_shared_config(self):
        config = load_settings()
        self.assertEqual(config["retrieval"]["retrieval_top_k"], 50)
        self.assertEqual(config["retrieval"]["result_top_k"], 10)
        self.assertEqual(config["hybrid"]["fusion"], "rrf")
        self.assertNotIn("candidate_k", config["hybrid"])

    def test_missing_retrieval_top_k_fails(self):
        config = copy.deepcopy(load_settings())
        del config["retrieval"]["retrieval_top_k"]
        with self.assertRaisesRegex(ValueError, "retrieval_top_k"):
            validate_settings(config)

    def test_result_top_k_cannot_exceed_retrieval_top_k(self):
        config = copy.deepcopy(load_settings())
        config["retrieval"]["result_top_k"] = 51
        with self.assertRaisesRegex(ValueError, "không được lớn hơn"):
            validate_settings(config)

    def test_unknown_default_model_fails(self):
        config = copy.deepcopy(load_settings())
        config["dense"]["model"] = "unknown/model"
        with self.assertRaisesRegex(ValueError, "chưa được đăng ký"):
            validate_settings(config)

    def test_dimension_must_match_default_model(self):
        config = copy.deepcopy(load_settings())
        config["dense"]["dimension"] = 768
        with self.assertRaisesRegex(ValueError, "không khớp model"):
            validate_settings(config)

    def test_only_rrf_fusion_is_supported(self):
        config = copy.deepcopy(load_settings())
        config["hybrid"]["fusion"] = "weighted"
        with self.assertRaisesRegex(ValueError, "chỉ hỗ trợ 'rrf'"):
            validate_settings(config)

    def test_invalid_yaml_file_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yaml"
            path.write_text("retrieval: [", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "YAML"):
                load_settings(path)

    def test_build_index_defaults_and_overrides_follow_shared_config(self):
        settings = load_settings()
        resolved = resolve_build_config(settings)
        self.assertEqual(resolved["model"], settings["dense"]["model"])
        self.assertEqual(resolved["collection"], settings["dense"]["collection"])
        self.assertEqual(resolved["input"].name, "chunks.jsonl")
        overridden = resolve_build_config(
            settings, input_override="custom/chunks.jsonl",
            model_override="bkai-foundation-models/vietnamese-bi-encoder",
            collection_override="custom-collection",
        )
        self.assertEqual(overridden["dimension"], 768)
        self.assertEqual(overridden["collection"], "custom-collection")

    def test_evaluator_rejects_non_rrf_fusion(self):
        config = copy.deepcopy(load_settings())
        config["hybrid"]["fusion"] = "weighted"
        with patch("retrieval.retrieval_evaluation.load_settings", return_value=config):
            with self.assertRaisesRegex(ValueError, "fusion=rrf"):
                evaluate(Path("missing-dev.json"), Path("missing-results"), Path("unused-output"))


if __name__ == "__main__":
    unittest.main()
