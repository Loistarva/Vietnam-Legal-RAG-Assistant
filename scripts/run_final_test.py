
import sys
from pathlib import Path

# Xác định thư mục gốc của project
ROOT_DIR = Path(__file__).resolve().parent.parent

# Thêm thư mục gốc vào Python path
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.benchmark_runner import run_benchmark_bm25


# Đường dẫn dữ liệu Dev Set
QUERIES_TEST_PATH = ROOT_DIR / "data" / "benchmark" / "queries_test.json"
RESULTS_PATH = ROOT_DIR / "evaluation" /"results"/ "bm25_test_results.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
METRICS_TEST_PATH = ROOT_DIR / "evaluation" /"results" /"bm25_test_metrics.json"

TOP_K = 5


if __name__ == "__main__":
    print("🎯 Bắt đầu chạy baseline benchmark cho BM25 trên TEST Set...\n")

    run_benchmark_bm25(
        queries_path=QUERIES_TEST_PATH,
        results_path=RESULTS_PATH,
        ground_truth_path=GROUND_TRUTH_PATH,
        metrics_path=METRICS_TEST_PATH,
        top_k=TOP_K,
    )
