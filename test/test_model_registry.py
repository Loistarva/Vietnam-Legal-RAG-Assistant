import copy
import unittest

from embedding.model_registry import ModelRegistry
from retrieval.settings import load_settings


class ModelRegistryTest(unittest.TestCase):
    def test_default_model_resolves_from_shared_config(self):
        model = ModelRegistry().get_default_model()
        self.assertEqual(model["name"], "BAAI/bge-m3")
        self.assertEqual(model["dimension"], 1024)

    def test_registered_model_has_its_own_dimension_and_preprocessing(self):
        model = ModelRegistry().get_model("bkai-foundation-models/vietnamese-bi-encoder")
        self.assertEqual(model["dimension"], 768)
        self.assertTrue(model["use_word_segmentation"])

    def test_unknown_model_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "supported_models"):
            ModelRegistry().get_model("missing/model")

    def test_custom_config_is_validated(self):
        config = copy.deepcopy(load_settings())
        config["dense"]["dimension"] = 768
        with self.assertRaisesRegex(ValueError, "không khớp model"):
            ModelRegistry(config)


if __name__ == "__main__":
    unittest.main()
