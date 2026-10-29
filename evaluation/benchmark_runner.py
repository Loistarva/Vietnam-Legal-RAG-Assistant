from pathlib import Path

from evaluation.bm25_baseline import run_bm25
from evaluation.metrics import evaluate


def run_benchmark_bm25(
    queries_path: str | Path,
    results_path: str | Path,
    ground_truth_path: str | Path,
    metrics_path: str | Path,
    *,
    top_k: int = 5,
    use_candidates: bool = False,
) -> None:
    """Chạy BM25 retrieval và đánh giá kết quả trên Dev Set."""

    queries_path = Path(queries_path)
    results_path = Path(results_path)
    ground_truth_path = Path(ground_truth_path)
    metrics_path = Path(metrics_path)

    # Tạo thư mục output nếu chưa tồn tại
    results_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    run_bm25(queries_path, results_path, top_k=top_k)
    evaluate(
        results_path,
        ground_truth_path,
        metrics_path,
        queries_paths=[queries_path],
        use_candidates=use_candidates,
    )
