import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.zero_shot import manifest_path_for, run_benchmark
from model_gateway.llm_gateway import QwenGatewayConfig
from schemas.models import LLMResponse


class FakeGateway:
    def __init__(self):
        self.config = QwenGatewayConfig()
        self.model_digest = "test-digest"
        self.ollama_version = "test-version"
        self.calls = 0

    def generate(self, prompt, query_id, run_mode, prompt_version):
        self.calls += 1
        return LLMResponse(
            query_id=query_id,
            run_mode=run_mode,
            answer="Câu trả lời.",
            prompt_version=prompt_version,
            done_reason="stop",
        )


class ZeroShotManifestTest(unittest.TestCase):
    def test_run_writes_provenance_manifest_and_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            questions_path = root / "questions.json"
            questions_path.write_text(
                json.dumps([{
                    "id": "HN_001",
                    "question": "Câu hỏi?",
                    "as_of_date": "2026-11-14",
                }]),
                encoding="utf-8",
            )
            output_path = root / "20261114_zero_shot_qwen25_dev30.jsonl"
            gateway = FakeGateway()

            results = run_benchmark(
                questions_path,
                output_path,
                gateway=gateway,
                split="dev",
            )

            manifest_path = manifest_path_for(output_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected_ids_hash = hashlib.sha256(b'["HN_001"]\n').hexdigest()
            self.assertEqual(len(results), 1)
            self.assertEqual(manifest["run_id"], output_path.stem)
            self.assertEqual(manifest["experiment"], "A_zero_shot")
            self.assertEqual(manifest["split"], "dev")
            self.assertEqual(manifest["dataset_ids_hash"], expected_ids_hash)
            self.assertEqual(manifest["as_of_date_source"], "benchmark")
            self.assertEqual(manifest["prompt_version"], "v1.2_zero_shot")
            self.assertEqual(manifest["runtime"]["model"], gateway.config.model)
            self.assertEqual(manifest["status"], "SUCCESS")
            self.assertEqual(manifest["total"], 1)
            self.assertEqual(manifest["succeeded"], 1)
            self.assertEqual(manifest["failed"], 0)
            self.assertEqual(len(output_path.read_text(encoding="utf-8").splitlines()), 1)

            with self.assertRaises(FileExistsError):
                run_benchmark(questions_path, output_path, gateway=gateway, split="dev")
            self.assertEqual(gateway.calls, 1)

    def test_existing_manifest_alone_blocks_a_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            questions_path = root / "questions.json"
            questions_path.write_text(
                json.dumps([{
                    "id": "HN_001",
                    "question": "Câu hỏi?",
                    "as_of_date": "2026-11-14",
                }]),
                encoding="utf-8",
            )
            output_path = root / "run.jsonl"
            manifest_path = manifest_path_for(output_path)
            manifest_path.write_text("existing manifest", encoding="utf-8")
            gateway = FakeGateway()

            with self.assertRaises(FileExistsError):
                run_benchmark(questions_path, output_path, gateway=gateway)

            self.assertEqual(gateway.calls, 0)
            self.assertFalse(output_path.exists())
            self.assertEqual(manifest_path.read_text(encoding="utf-8"), "existing manifest")


if __name__ == "__main__":
    unittest.main()
