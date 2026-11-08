"""Regression tests for parser/cleaner.py.

The cleaner must reproduce every committed parser/cleaned_texts/*.txt from
parser/extracted_texts_qwen/*.txt, and it must only delete noise lines
(page counters, Công báo markings, URLs, export timestamps), never legal wording.

Run from the repository root:
    python -m pytest parser/test_cleaner.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pytest

PARSER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PARSER_DIR))

import cleaner  # noqa: E402

RAW_FILES = sorted((PARSER_DIR / "extracted_texts_qwen").glob("*.txt"))
WORD_RE = re.compile(r"\w+")


def test_cleaner_imports_without_ocr_dependencies():
    assert "ollama" not in vars(cleaner)
    assert "pymupdf" not in vars(cleaner)


@pytest.mark.parametrize("raw_path", RAW_FILES, ids=lambda p: p.name)
def test_cleaner_reproduces_committed_cleaned_text(raw_path: Path):
    cleaned, _ = cleaner.clean_extracted_text(raw_path.read_text(encoding="utf-8"))
    committed = PARSER_DIR / "cleaned_texts" / raw_path.name
    assert committed.exists(), f"Thiếu {committed.name} trong cleaned_texts"
    assert committed.read_text(encoding="utf-8") == cleaned + "\n", (
        f"cleaned_texts/{raw_path.name} không khớp kết quả của cleaner hiện tại"
    )


@pytest.mark.parametrize("raw_path", RAW_FILES, ids=lambda p: p.name)
def test_cleaner_only_removes_noise_words(raw_path: Path):
    raw = cleaner.normalize_extracted_text(raw_path.read_text(encoding="utf-8"))
    raw, _ = cleaner.normalize_vietnamese_tone_placement(cleaner.unicodedata.normalize("NFC", raw))
    cleaned, _ = cleaner.clean_extracted_text(raw_path.read_text(encoding="utf-8"))

    removed = Counter(WORD_RE.findall(raw)) - Counter(WORD_RE.findall(cleaned))
    noise_lines = [
        line for line in raw.splitlines()
        if cleaner.GAZETTE_MARKER_RE.search(line)
        or cleaner.URL_RE.search(line)
        or cleaner.TIMESTAMP_RE.search(line)
        or cleaner.PAGE_COUNTER_RE.fullmatch(line.strip())
        or cleaner.SINGLE_PAGE_LABEL_RE.fullmatch(line.strip())
        or cleaner.STANDALONE_NUMBER_RE.fullmatch(line.strip())
    ]
    allowed = Counter(WORD_RE.findall("\n".join(noise_lines)))
    unexpected = removed - allowed
    assert not unexpected, f"Cleaner xóa từ ngoài dòng nhiễu: {list(unexpected.items())[:10]}"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("a, Giấy tờ của cơ quan nước ngoài", "a) Giấy tờ của cơ quan nước ngoài"),
        ("đ, Đối với trường hợp khác", "đ) Đối với trường hợp khác"),
        ("2.Giấy tờ bằng tiếng nước ngoài", "2. Giấy tờ bằng tiếng nước ngoài"),
        # Dẫn chiếu xuống dòng, không phải nhãn Điểm: giữ nguyên.
        ("b, c và d khoản 2 Điều 5 của Luật này.", "b, c và d khoản 2 Điều 5 của Luật này."),
        ("a, b, c, d và đ khoản 2 Điều 44 của Nghị định này.", "a, b, c, d và đ khoản 2 Điều 44 của Nghị định này."),
        ("1.1- Theo quy định tại Điều 1", "1.1- Theo quy định tại Điều 1"),
        ("a) Giấy tờ đúng nhãn", "a) Giấy tờ đúng nhãn"),
    ],
)
def test_label_punctuation_is_normalized_only_before_uppercase(line: str, expected: str):
    assert cleaner.normalize_label_punctuation(line)[0] == expected


@pytest.mark.parametrize("raw_path", RAW_FILES, ids=lambda p: p.name)
def test_cleaned_text_has_no_malformed_labels(raw_path: Path):
    """Nhãn "a," hay "2.Giấy" làm chunker không nhận ra Điểm/Khoản và cắt theo cửa sổ giữa câu."""
    committed = (PARSER_DIR / "cleaned_texts" / raw_path.name).read_text(encoding="utf-8")
    bad = [line for line in committed.splitlines() if cleaner.normalize_label_punctuation(line)[1]]
    assert not bad, f"{raw_path.name}: nhãn Điểm/Khoản sai kiểu: {bad[:5]}"


# --- H8: trang hoặc file lỗi phải làm cleaner báo lỗi, không âm thầm dùng text gốc ---

class _FakePage:
    def __init__(self, text: str, images: bool = False, broken: bool = False):
        self.text = text
        self.images = images
        self.broken = broken

    def get_text(self, mode: str, sort: bool = False):
        if self.broken:
            raise RuntimeError("bad page")
        if mode == "dict":
            return {"blocks": [{"type": 1}] if self.images else []}
        return self.text


class _FakeDoc(list):
    def close(self):
        pass


def _fake_pymupdf(pages):
    import types
    return types.SimpleNamespace(open=lambda path: _FakeDoc(pages))


LONG_TEXT = "Điều 1. Phạm vi điều chỉnh. " * 10


def test_page_with_failed_ocr_is_reported(monkeypatch):
    monkeypatch.setattr(cleaner, "qwen_transcribe_page", lambda *a: "")
    assert cleaner.process_page(_FakePage("Trang 2"), 2, "x") == ("Trang 2", "ocr_failed")
    assert cleaner.process_page(_FakePage("", images=True), 3, "x") == ("", "ocr_failed")


def test_page_uses_ocr_or_native_text(monkeypatch):
    monkeypatch.setattr(cleaner, "qwen_transcribe_page", lambda *a: "Điều 2. OCR")
    assert cleaner.process_page(_FakePage("ngắn"), 1, "x") == ("Điều 2. OCR", "qwen3-vl")
    monkeypatch.setattr(cleaner, "qwen_transcribe_page", lambda *a: pytest.fail("không cần OCR"))
    assert cleaner.process_page(_FakePage(LONG_TEXT), 1, "x")[1] == "pymupdf"
    assert cleaner.process_page(_FakePage(""), 1, "x") == ("", "empty")


def test_page_has_images_survives_unreadable_blocks():
    assert cleaner.page_has_images(_FakePage("", broken=True)) is False


@pytest.mark.parametrize(
    ("ocr_result", "expected"),
    [("Điều 2. Nội dung trang quét", True), ("", False)],
)
def test_process_pdf_fails_when_a_page_fails(monkeypatch, tmp_path, ocr_result, expected):
    monkeypatch.setitem(sys.modules, "pymupdf", _fake_pymupdf([_FakePage(LONG_TEXT), _FakePage("", images=True)]))
    monkeypatch.setattr(cleaner, "qwen_transcribe_page", lambda *a: ocr_result)
    assert cleaner.process_pdf(tmp_path / "a.pdf", tmp_path / "raw" / "a.txt", tmp_path / "clean" / "a.txt") is expected


def test_process_pdf_fails_on_unreadable_page(monkeypatch, tmp_path):
    class _BrokenDoc(_FakeDoc):
        def __iter__(self):
            raise RuntimeError("FileDataError")

    import types
    monkeypatch.setitem(sys.modules, "pymupdf", types.SimpleNamespace(open=lambda path: _BrokenDoc()))
    assert cleaner.process_pdf(tmp_path / "a.pdf", tmp_path / "raw.txt", tmp_path / "clean.txt") is False
    assert not (tmp_path / "raw.txt").exists()


def test_clean_existing_texts_lists_failed_files(monkeypatch, tmp_path):
    raw_dir, out_dir = tmp_path / "raw", tmp_path / "clean"
    raw_dir.mkdir()
    (raw_dir / "good.txt").write_text(LONG_TEXT, encoding="utf-8")
    (raw_dir / "bad.txt").write_bytes(b"\xff\xfe\x00 not utf-8 \xc3")
    monkeypatch.setattr(cleaner, "RAW_OUTPUT_DIR", raw_dir)
    monkeypatch.setattr(cleaner, "OUTPUT_DIR", out_dir)
    summary = cleaner.clean_existing_texts()
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1 and summary["failed_files"] == ["bad.txt"]


@pytest.mark.parametrize(("failed", "code"), [(0, 0), (2, 1)])
def test_main_exit_code_reflects_failures(monkeypatch, failed, code):
    summary = {"succeeded": 1, "failed": failed, "failed_files": ["x.pdf"] * failed, "total": 1 + failed}
    monkeypatch.setattr(cleaner, "clean_existing_texts", lambda: summary)
    monkeypatch.setattr(cleaner, "run_cleaner", lambda: summary)
    assert cleaner.main(["--clean-existing"]) == code
    assert cleaner.main([]) == code
