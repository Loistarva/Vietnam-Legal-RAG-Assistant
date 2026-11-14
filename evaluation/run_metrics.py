"""Shared command-line implementation for evaluating saved Run A/B answers."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from evaluation.citation_parser import parse_zero_shot_file
from evaluation.evaluate_zero_shot import evaluate as evaluate_answer_text
from evaluation.metrics import evaluate_answer_run

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GROUND_TRUTH = ROOT / "data" / "benchmark" / "ground_truth.json"
DEFAULT_RUN_A_INPUT = ROOT / "evaluation" / "results" / "zero_shot_dev30_results.json"
DEFAULT_RUN_B_INPUT = (
    ROOT / "evaluation" / "results" / "dev"
    / "20261114_controlled_rag_qwen25_dev30_prompt_v1_2" / "results.jsonl"
)


def read_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        records = json.loads(text)
    except json.JSONDecodeError:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError(f"{path} must contain a JSON array or JSONL objects")
    return records


def evaluate_saved_run(run: str, argv: list[str] | None = None) -> None:
    run = run.upper()
    parser = argparse.ArgumentParser(
        description=f"Evaluate saved Run {run} results only; does not generate answers.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    default_input = DEFAULT_RUN_A_INPUT if run == "A" else DEFAULT_RUN_B_INPUT
    parser.add_argument("--input", type=Path, default=default_input,
                        help="Run A results JSON" if run == "A" else "Run B results JSONL")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--queries", type=Path,
                        help="Optional benchmark query JSON for category/as_of_date metadata")
    parser.add_argument("--output", type=Path,
                        help="Metrics JSON; defaults beside the input file")
    if run == "A":
        parser.add_argument("--parsed-output", type=Path,
                            help="Parser artifact path; defaults to <input>_parsed.json")
    args = parser.parse_args(argv)

    input_path = args.input
    if run == "A":
        records = read_records(input_path)
        parsed = bool(records) and isinstance(records[0].get("result"), dict) and isinstance(
            records[0]["result"].get("citations"), list
        )
        if not parsed:
            parsed_path = args.parsed_output or input_path.with_name(
                f"{input_path.stem}_parsed.json"
            )
            parse_zero_shot_file(input_path, parsed_path)
            input_path = parsed_path
            print(f"Run A parsed output: {parsed_path.resolve()}")

    records = read_records(input_path)
    ground_truth = json.loads(args.ground_truth.read_text(encoding="utf-8-sig"))
    if not isinstance(ground_truth, list):
        raise ValueError("ground truth must contain a JSON array")
    report = evaluate_answer_run(records, ground_truth, run=run)

    # Include existing automatic answer-overlap metrics. No manual rubric is read.
    with tempfile.TemporaryDirectory(prefix="answer-run-metrics-") as temp_dir:
        temp_root = Path(temp_dir)
        normalized_path = temp_root / "records.json"
        normalized_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        query_source: list[dict[str, Any]] = []
        if args.queries:
            loaded_queries = json.loads(args.queries.read_text(encoding="utf-8-sig"))
            if isinstance(loaded_queries, list):
                query_source = [q for q in loaded_queries if isinstance(q, dict)]
        source_by_id = {q["id"]: q for q in query_source if isinstance(q.get("id"), str)}
        query_rows = []
        for envelope in records:
            row = envelope.get("result") if isinstance(envelope.get("result"), dict) else envelope
            query_id = row.get("query_id") or envelope.get("query_id") or row.get("id")
            if not isinstance(query_id, str):
                continue
            source = source_by_id.get(query_id, {})
            query_rows.append({
                **source,
                "id": query_id,
                "question": source.get("question") or row.get("query") or row.get("question") or "",
                "as_of_date": source.get("as_of_date") or row.get("as_of_date") or envelope.get("as_of_date"),
                "category": source.get("category") or row.get("category"),
            })
        query_path = temp_root / "selected_queries.json"
        query_path.write_text(json.dumps(query_rows, ensure_ascii=False), encoding="utf-8")
        answer_summary = evaluate_answer_text(
            predictions_path=normalized_path,
            ground_truth_path=args.ground_truth,
            metrics_output_path=temp_root / "answer_metrics.json",
            scored_output_path=temp_root / "answer_scored.json",
            queries_paths=[query_path],
        )
    for key in (
        "exact_match", "token_f1", "lexical_relevance", "lexical_faithfulness",
        "lexical_relevance_score", "lexical_faithfulness_score",
        "lexical_scored_questions", "evaluated_questions",
        "prediction_ids_without_reference", "ground_truth_ids_without_prediction",
    ):
        if key in answer_summary:
            report[key] = answer_summary[key]

    metrics_dir = ROOT / "evaluation" / "results" / "metrics_A_B_results"
    output_path = args.output or metrics_dir / f"{args.input.stem}_metrics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Run {run} metrics: {output_path.resolve()}")
