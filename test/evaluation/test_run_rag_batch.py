"""Tests for batch preparation, resume bookkeeping, and JSONL output."""
from __future__ import annotations

import json

import pytest

from scripts.run_rag_batch import (
    BatchInputError,
    JsonlWriter,
    build_benchmark_index,
    execute_batch,
    filter_pending_queries,
    load_benchmark,
    load_completed_query_ids,
    load_ids_from_jsonl,
    load_ids_from_txt,
    main,
    normalize_input_ids,
    prepare_batch,
    resolve_query,
    validate_query,
)


def test_load_ids_from_txt(tmp_path):
    source = tmp_path / "ids.txt"
    source.write_text("HN_001\n\n HN_002 \n", encoding="utf-8")
    ids, errors = load_ids_from_txt(source)
    assert ids == ["HN_001", "HN_002"]
    assert errors == []


def test_load_ids_from_jsonl_and_report_malformed_line(tmp_path):
    source = tmp_path / "ids.jsonl"
    source.write_text(
        '{"query_id":"HN_001"}\nnot-json\n{"query_id":"HN_002"}\n',
        encoding="utf-8",
    )
    ids, errors = load_ids_from_jsonl(source)
    assert ids == ["HN_001", "HN_002"]
    assert len(errors) == 1
    assert errors[0].line == 2


def test_remove_duplicate_ids_preserving_first_occurrence_and_reject_invalid():
    ids, errors, initial_count = normalize_input_ids(
        [" HN_001 ", "HN_001", "", None, "HN_002"]
    )
    assert ids == ["HN_001", "HN_002"]
    assert initial_count == 5
    assert len(errors) == 2


def test_load_benchmark_and_build_index(tmp_path):
    source = tmp_path / "queries.json"
    source.write_text(
        json.dumps([{"id": "HN_001", "question": "Q?", "as_of_date": "2020-01-01"}]),
        encoding="utf-8",
    )
    index = build_benchmark_index(load_benchmark(source))
    assert list(index) == ["HN_001"]


def test_duplicate_benchmark_ids_are_rejected():
    rows = [
        {"id": "HN_001", "question": "one", "as_of_date": "2020-01-01"},
        {"id": "HN_001", "question": "two", "as_of_date": "2020-01-01"},
    ]
    with pytest.raises(BatchInputError, match="nhiều lần"):
        build_benchmark_index(rows)


def test_resolve_query_uses_text_and_date_from_exact_benchmark_id():
    index = {
        "HN_001": {
            "id": "HN_001",
            "question": "Câu hỏi 1?",
            "as_of_date": "2014-06-01",
        }
    }
    assert resolve_query("HN_001", index) == {
        "query_id": "HN_001",
        "query": "Câu hỏi 1?",
        "as_of_date": "2014-06-01",
    }


def test_unknown_query_id_is_reported_and_not_resolved(tmp_path):
    queries, errors, _ = prepare_batch_fixture(
        tmp_path=tmp_path,
        ids="HN_MISSING\n",
    )
    assert queries == []
    assert len(errors) == 1
    assert errors[0].query_id == "HN_MISSING"


def prepare_batch_fixture(tmp_path, ids):
    """Build a tiny benchmark/input pair in pytest's temporary directory."""
    input_path = tmp_path / "ids.txt"
    benchmark_path = tmp_path / "benchmark.json"
    input_path.write_text(ids, encoding="utf-8")
    benchmark_path.write_text(
        json.dumps(
            [{"id": "HN_001", "question": "Câu hỏi?", "as_of_date": "2020-01-01"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return prepare_batch(input_path, benchmark_path)


def test_invalid_as_of_date_is_rejected():
    with pytest.raises(BatchInputError, match="as_of_date không hợp lệ"):
        validate_query(
            {"query_id": "HN_001", "query": "Câu hỏi?", "as_of_date": "08/11/2026"}
        )


def test_empty_or_non_string_question_is_rejected():
    for question in ("", "  ", 17, None):
        with pytest.raises(BatchInputError, match="question"):
            validate_query(
                {"query_id": "HN_001", "query": question, "as_of_date": "2020-01-01"}
            )


def test_resume_skips_only_valid_success_records_and_retries_errors(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text(
        '\n'.join(
            [
                json.dumps({"status": "SUCCESS", "query_id": "HN_001", "result": {"answer": "ok"}}),
                json.dumps({"status": "ERROR", "query_id": "HN_002", "result": {}}),
                json.dumps({"status": "SUCCESS", "query_id": "HN_003", "result": "invalid-shape"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    completed = load_completed_query_ids(results)
    assert completed == {"HN_001"}
    pending, skipped = filter_pending_queries(
        [{"query_id": "HN_001"}, {"query_id": "HN_002"}, {"query_id": "HN_004"}],
        completed,
    )
    assert [item["query_id"] for item in pending] == ["HN_002", "HN_004"]
    assert skipped == 1


def test_retry_failed_queries(tmp_path):
    results = tmp_path / "results.jsonl"
    writer = JsonlWriter(results, tmp_path / "errors.jsonl")
    writer.write_error("HN_001", "first attempt failed")
    assert load_completed_query_ids(results) == set()


def test_write_jsonl_preserves_vietnamese_and_record_fields(tmp_path):
    results = tmp_path / "results.jsonl"
    query = {"query_id": "HN_001", "query": "Câu hỏi tiếng Việt?", "as_of_date": "2020-01-01"}
    JsonlWriter(results, tmp_path / "errors.jsonl").write_success(
        query, {"answer": "Quyền và nghĩa vụ"}
    )
    raw = results.read_text(encoding="utf-8")
    assert "Quyền và nghĩa vụ" in raw
    record = json.loads(raw)
    assert record["result"] == {"answer": "Quyền và nghĩa vụ"}
    assert record["query_id"] == "HN_001"


def test_append_without_overwrite(tmp_path):
    results = tmp_path / "results.jsonl"
    writer = JsonlWriter(results, tmp_path / "errors.jsonl")
    query1 = {"query_id": "HN_001", "as_of_date": "2020-01-01"}
    query2 = {"query_id": "HN_002", "as_of_date": "2020-01-01"}
    writer.write_success(query1, {"answer": "one"})
    writer.write_success(query2, {"answer": "two"})
    assert len(results.read_text(encoding="utf-8").splitlines()) == 2
    assert load_completed_query_ids(results) == {"HN_001", "HN_002"}
    stats = execute_batch(
        [query1, query2],
        lambda _query: pytest.fail("completed results must not be rerun"),
        writer,
    )
    assert stats == {"succeeded": 0, "failed": 0, "skipped": 2}
    assert len(results.read_text(encoding="utf-8").splitlines()) == 2


def test_error_isolated_per_query_and_batch_continues(tmp_path):
    queries = [
        {"query_id": f"HN_{number:03}", "query": f"Câu {number}", "as_of_date": "2020-01-01"}
        for number in range(1, 4)
    ]

    def local_runner(query):
        if query["query_id"] == "HN_002":
            raise RuntimeError("lỗi riêng của query thứ hai")
        return {"echo_query_id": query["query_id"]}

    writer = JsonlWriter(tmp_path / "results.jsonl", tmp_path / "errors.jsonl")
    stats = execute_batch(queries, local_runner, writer)
    assert stats == {"succeeded": 2, "failed": 1, "skipped": 0}
    assert load_completed_query_ids(tmp_path / "results.jsonl") == {"HN_001", "HN_003"}
    error_record = json.loads((tmp_path / "errors.jsonl").read_text(encoding="utf-8"))
    assert error_record["query_id"] == "HN_002"


def test_prepare_batch_uses_benchmark_as_of_date_not_input_values(tmp_path):
    input_path = tmp_path / "ids.jsonl"
    input_path.write_text(
        '{"query_id":"HN_001","question":"tampered","as_of_date":"1999-01-01"}\n',
        encoding="utf-8",
    )
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(
        json.dumps([{"id": "HN_001", "question": "Nguồn chuẩn?", "as_of_date": "2020-01-01"}]),
        encoding="utf-8",
    )
    queries, errors, _ = prepare_batch(input_path, benchmark_path)
    assert not errors
    assert queries == [
        {"query_id": "HN_001", "query": "Nguồn chuẩn?", "as_of_date": "2020-01-01"}
    ]


def test_cli_prepare_only_resolves_queries_without_output_files(tmp_path, capsys):
    input_path = tmp_path / "ids.txt"
    benchmark_path = tmp_path / "benchmark.json"
    input_path.write_text("HN_001\n", encoding="utf-8")
    benchmark_path.write_text(
        json.dumps([{"id": "HN_001", "question": "Câu hỏi?", "as_of_date": "2020-01-01"}]),
        encoding="utf-8",
    )
    output_dir = tmp_path / "batch-output"
    status = main(
        [
            "--input", str(input_path), "--benchmark", str(benchmark_path),
            "--prepare-only",
        ]
    )
    captured = capsys.readouterr()
    assert status == 0
    assert "READY HN_001 as_of_date=2020-01-01" in captured.out
    assert not output_dir.exists()


def test_cli_refuses_execution_without_dev5_runner_adapter(tmp_path, capsys):
    input_path = tmp_path / "ids.txt"
    input_path.write_text("HN_001\n", encoding="utf-8")
    status = main(["--input", str(input_path)])
    captured = capsys.readouterr()
    assert status == 2
    assert "adapter Dev5" in captured.err
