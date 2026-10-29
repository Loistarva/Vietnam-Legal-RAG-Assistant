import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Xác định thư mục gốc của project
ROOT_DIR = Path(__file__).resolve().parent.parent

# Thêm thư mục gốc vào Python path
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.benchmark_runner import run_benchmark_bm25


# Đường dẫn dữ liệu Dev Set
QUERIES_DEV_PATH = ROOT_DIR / "data" / "benchmark" / "queries_dev.json"
RESULTS_PATH = ROOT_DIR / "evaluation" / "results" / "bm25_dev_results.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
METRICS_PATH = ROOT_DIR / "evaluation" / "results" / "bm25_dev_metrics.json"

TOP_K = 5


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy baseline benchmark cho BM25 trên Dev Set.")
    parser.add_argument("--queries", type=Path, default=QUERIES_DEV_PATH, help="Đường dẫn queries Dev")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH, help="Đường dẫn file kết quả retrieval")
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH, help="Đường dẫn ground_truth.json")
    parser.add_argument("--metrics", type=Path, default=METRICS_PATH, help="Đường dẫn lưu file metrics")
    parser.add_argument("--top-k", type=int, default=TOP_K, help="Số lượng kết quả top K")
    parser.add_argument(
        "--use-candidates",
        action="store_true",
        help=(
            "Chấm câu chưa có gold bằng candidate_context_ids (chưa duyệt, chỉ là số tham khảo); "
            "mặc định chỉ chấm câu có gold_context_ids"
        ),
    )
    args = parser.parse_args()

    # Số đo trên candidate không được ghi đè file metric chấm trên gold
    if args.use_candidates and args.metrics == METRICS_PATH:
        args.metrics = METRICS_PATH.with_name(f"{METRICS_PATH.stem}_candidates{METRICS_PATH.suffix}")

    print("🎯 Bắt đầu chạy baseline benchmark cho BM25 trên Dev Set...\n")

    run_benchmark_bm25(
        queries_path=args.queries,
        results_path=args.results,
        ground_truth_path=args.ground_truth,
        metrics_path=args.metrics,
        top_k=args.top_k,
        use_candidates=args.use_candidates,
    )


if __name__ == "__main__":
    main()
