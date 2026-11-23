import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.zero_shot import ROOT, _sha256_file, manifest_path_for, run_benchmark
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
            self.assertEqual(
                manifest["results_sha256"],
                hashlib.sha256(output_path.read_bytes()).hexdigest(),
            )
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


class ZeroShotChecksumTest(unittest.TestCase):
    def test_file_hash_ignores_crlf_checkout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lf_path = Path(temp_dir) / "lf.jsonl"
            crlf_path = Path(temp_dir) / "crlf.jsonl"
            lf_path.write_bytes(b'{"a": 1}\n{"b": 2}\n')
            crlf_path.write_bytes(b'{"a": 1}\r\n{"b": 2}\r\n')

            self.assertEqual(_sha256_file(crlf_path), _sha256_file(lf_path))
            self.assertEqual(
                _sha256_file(lf_path),
                hashlib.sha256(lf_path.read_bytes()).hexdigest(),
            )

    def test_committed_run_a_manifests_match_checked_out_files(self):
        manifests = sorted((ROOT / "evaluation" / "results" / "dev").glob(
            "*_zero_shot_qwen25_dev30_manifest.json"
        ))
        self.assertTrue(manifests)
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            results_path = manifest_path.with_name(f"{manifest['run_id']}.jsonl")
            with self.subTest(manifest=manifest_path.name):
                self.assertEqual(manifest["results_sha256"], _sha256_file(results_path))


if __name__ == "__main__":
    unittest.main()
