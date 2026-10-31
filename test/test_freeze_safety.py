import json
import importlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import freeze_gold, freeze_test


class FreezeManifestSafetyTest(unittest.TestCase):
    def test_test_question_freeze_refuses_to_replace_existing_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "freeze.json"
            original = {"sha256": "old-test-freeze"}
            path.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(freeze_test, "MANIFEST", path), patch.object(
                freeze_test, "manifest", return_value={"sha256": "new-test-freeze"}
            ):
                with self.assertRaisesRegex(RuntimeError, "dùng --force"):
                    freeze_test.run("create")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)

    def test_gold_freeze_refuses_to_replace_existing_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "freeze.json"
            original = {"sha256": "old-gold-freeze"}
            path.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(freeze_gold, "MANIFEST", path), patch.object(
                freeze_gold, "current", return_value={"sha256": "new-gold-freeze"}
            ):
                with self.assertRaisesRegex(RuntimeError, "dùng --force"):
                    freeze_gold.run("create")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)

    def test_gold_create_rechecks_readiness_before_idempotent_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "freeze.json"
            candidate = {"sha256": "same-gold-freeze", "test_question_count": 30}
            path.write_text(json.dumps(candidate), encoding="utf-8")
            with patch.object(freeze_gold, "MANIFEST", path), patch.object(
                freeze_gold, "current", return_value=candidate
            ), patch.object(freeze_gold, "verify_test_split_ready", return_value=["gold chunk thiếu"]), patch.object(
                freeze_gold, "check"
            ) as check:
                with self.assertRaisesRegex(RuntimeError, "Chưa thể khóa"):
                    freeze_gold.run("create")
                check.assert_not_called()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), candidate)

    def test_gold_create_does_not_write_when_structural_check_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "freeze.json"
            candidate = {"sha256": "new-gold-freeze"}
            with patch.object(freeze_gold, "MANIFEST", path), patch.object(
                freeze_gold, "current", return_value=candidate
            ), patch.object(freeze_gold, "verify_test_split_ready", return_value=[]), patch.object(
                freeze_gold, "check", return_value=(['invalid benchmark structure'], [], [])
            ):
                with self.assertRaisesRegex(RuntimeError, "Lỗi cấu trúc"):
                    freeze_gold.run("create")
            self.assertFalse(path.exists())

    def test_gold_force_replaces_manifest_after_real_validator_hash_warning(self):
        validator = importlib.import_module(freeze_gold.check.__module__)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            schemas = root / "schemas"
            docs.mkdir()
            schemas.mkdir()
            shutil.copy2(Path("docs/test_questions_freeze.json"), docs / "test_questions_freeze.json")
            shutil.copy2(Path("schemas/benchmark_schema.json"), schemas / "benchmark_schema.json")
            manifest_path = docs / "test_gold_freeze.json"
            manifest_path.write_text(json.dumps({"sha256": "old-hash"}), encoding="utf-8")
            with patch.object(validator, "ROOT", root), patch.object(freeze_gold, "MANIFEST", manifest_path), patch.object(
                freeze_gold, "verify_test_split_ready", return_value=[]
            ):
                freeze_gold.run("create", force=True)
            self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8")), freeze_gold.current())

    def test_gold_create_keeps_matching_manifest_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "freeze.json"
            candidate = {"sha256": "same-gold-freeze", "test_question_count": 30}
            original_bytes = json.dumps(candidate).encode("utf-8")
            path.write_bytes(original_bytes)
            with patch.object(freeze_gold, "MANIFEST", path), patch.object(
                freeze_gold, "current", return_value=candidate
            ), patch.object(freeze_gold, "verify_test_split_ready", return_value=[]), patch.object(
                freeze_gold, "check", return_value=([], [], [])
            ) as check, patch.object(Path, "write_text", side_effect=AssertionError("must not rewrite")):
                freeze_gold.run("create")
                check.assert_called_once_with(final=False)
            self.assertEqual(path.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
