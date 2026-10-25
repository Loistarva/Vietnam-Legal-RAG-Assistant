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
