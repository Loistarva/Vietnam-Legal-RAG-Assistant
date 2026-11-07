"""
Hybrid PDF extractor and post-extraction cleaner for Vietnam-Legal-RAG-Assistant.

Pipeline:
1. Extract text from each PDF page using PyMuPDF or Qwen3-VL.
2. Save the extracted text unchanged (apart from basic whitespace normalization)
   to parser/extracted_texts_qwen/<name>.txt for auditing/debugging.
3. Clean Công báo markings, likely website URLs, export timestamps, and standalone page counters.
4. Save the cleaned text to parser/cleaned_texts/<name>.txt for the parser.

Important: this script does not remove legal footnotes, citations, chapter headings,
article numbers, or legal wording. Structural fixes (e.g. a chapter heading appended
inside a clause) should be handled by the parser, not by this cleaner.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
import argparse
from pathlib import Path
from typing import Optional

# ollama và pymupdf chỉ được import khi trích xuất PDF, để các hàm làm sạch text
# import được (và test được) trên máy không cài hai thư viện này.

# Project paths: keep the existing cleaned output path for downstream compatibility.
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw_data"
RAW_OUTPUT_DIR = Path(__file__).resolve().parent / "extracted_texts_qwen"
OUTPUT_DIR = Path(__file__).resolve().parent / "cleaned_texts"
SUB_FOLDERS = ["circulars", "laws_and_decrees","additional_documents"]


MODEL_NAME = "qwen3-vl:8b-instruct"
OLLAMA_KEEP_ALIVE = "10m"
RENDER_DPI = 180
OCR_RETRIES = 1  # Retry once after an empty response or transient error.
FAILED_OCR_DIR = OUTPUT_DIR / "_ocr_failed_pages"

# If a page has fewer than this many extracted characters, treat it as possibly scanned.
MIN_TEXT_CHARS = 80

# Avoid reprocessing successful outputs. Set False to regenerate both raw and clean TXT.
SKIP_EXISTING_OUTPUTS = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("hybrid_pdf_cleaner")

OCR_PROMPT = """Bạn đang chép lại nội dung từ một trang văn bản pháp luật tiếng Việt.
Hãy chép lại TOÀN BỘ phần chữ nhìn thấy trên trang theo đúng thứ tự đọc từ trên xuống dưới.

Yêu cầu bắt buộc:
- Giữ nguyên nội dung pháp lý, số điều, khoản, điểm, số hiệu văn bản, ngày tháng và dấu câu.
- Không tóm tắt, không diễn giải, không tự sửa câu chữ theo suy đoán.
- Giữ các tiêu đề, nhãn, nội dung trong bảng và chú thích có thể đọc được.
- Không tự thêm nội dung không nhìn thấy.
- Nếu có một phần không thể đọc được, ghi [KHÔNG ĐỌC RÕ] tại vị trí đó.
- Chỉ trả về phần văn bản đã chép, không giải thích quy trình.
"""

# Only remove clear export/web noise. Do not remove ordinary legal footnotes.
URL_RE = re.compile(r"(?:https?://|www\.)\S+", flags=re.IGNORECASE)
# Common browser/export timestamps, e.g. 10/16/26, 1:12 AM or 16/10/2026 13:12.
TIMESTAMP_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*,?\s*"
    r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b",
    flags=re.IGNORECASE,
)
# Page counters are removed only when they form a standalone line after noise removal.
PAGE_COUNTER_RE = re.compile(
    r"^(?:(?:trang|page)\s*)?\d{1,4}\s*(?:/|of)\s*\d{1,4}$",
    flags=re.IGNORECASE,
)
SINGLE_PAGE_LABEL_RE = re.compile(r"^(?:trang|page)\s+\d{1,4}$", flags=re.IGNORECASE)
# Công báo footer/marking found in official-gazette PDF exports. Match the marker
# and its publication number/date through the end of the same line.
GAZETTE_MARKER_RE = re.compile(r"CÔNG\s+BÁO\s*/\s*SỐ\b", flags=re.IGNORECASE)
STANDALONE_NUMBER_RE = re.compile(r"^\d{1,4}$")
# Nhãn gõ sai kiểu ở đầu dòng: "a, Giấy tờ" -> "a) Giấy tờ", "2.Giấy tờ" -> "2. Giấy tờ".
# Chỉ sửa khi chữ ngay sau nhãn viết hoa, nên dẫn chiếu bị xuống dòng như
# "b, c và d khoản 2 Điều 5" giữ nguyên.
POINT_LABEL_COMMA_RE = re.compile(r"^([a-zđ]), (?=\w)")
CLAUSE_LABEL_NO_SPACE_RE = re.compile(r"^(\d{1,3})\.(?=\w)")

def normalize_extracted_text(text: str) -> str:
    """Basic normalization only; preserve wording for the raw extraction file."""
    text = text.replace("\x00", "")
    text = text.replace("\u00ad", "")  # soft hyphen
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



# Dấu thanh kiểu cũ trong âm tiết mở: hoà -> hòa, toà -> tòa, thuỷ -> thủy.
# Chỉ đổi oa/oe/uy khi âm tiết kết thúc bằng nguyên âm; bỏ qua qu-.
TONE_MARKS = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}
VOWELS = set("aeiouyAEIOUY")


def normalize_vietnamese_tone_placement(text: str) -> tuple[str, int]:
    """Move tone from the second vowel to the first in open oa/oe/uy syllables.

    Does not alter punctuation, syllables with a final consonant, or qu- syllables.
    Returns normalized text and the number of changed syllables.
    """
    changed = 0
    token_re = re.compile(r"[^\W\d_]+", flags=re.UNICODE)

    def normalize_word(match: re.Match[str]) -> str:
        nonlocal changed
        word = match.group(0)
        # Work on decomposed characters so Vietnamese tone marks are explicit.
        nfd = unicodedata.normalize("NFD", word)
        if nfd[:2].lower() == "qu":
            return word

        # Parse each base letter with its combining marks.
        chars: list[tuple[str, list[str]]] = []
        for ch in nfd:
            if unicodedata.combining(ch) and chars:
                chars[-1][1].append(ch)
            else:
                chars.append((ch, []))

        # Open syllable means the word ends in a vowel.
        if not chars or chars[-1][0] not in VOWELS:
            return word

        # Find the final vowel sequence; target only oa, oe, uy.
        vowel_indices = [i for i, (base, _) in enumerate(chars) if base in VOWELS]
        if len(vowel_indices) < 2:
            return word
        i, j = vowel_indices[-2], vowel_indices[-1]
        pair = (chars[i][0] + chars[j][0]).lower()
        if pair not in {"oa", "oe", "uy"} or j != len(chars) - 1:
            return word

        first_marks, second_marks = chars[i][1], chars[j][1]
        tone = next((mark for mark in second_marks if mark in TONE_MARKS), None)
        if tone is None or any(mark in TONE_MARKS for mark in first_marks):
            return word

        second_marks.remove(tone)
        first_marks.append(tone)
        changed += 1
        normalized = "".join(base + "".join(marks) for base, marks in chars)
        return unicodedata.normalize("NFC", normalized)

    normalized_text = token_re.sub(normalize_word, text)
    return normalized_text, changed


def normalize_label_punctuation(line: str) -> tuple[str, int]:
    """Đổi nhãn Điểm "a," thành "a)" và thêm dấu cách sau nhãn Khoản "2."; trả về số nhãn đã sửa."""
    for pattern, replacement in ((POINT_LABEL_COMMA_RE, r"\1) "), (CLAUSE_LABEL_NO_SPACE_RE, r"\1. ")):
        match = pattern.match(line)
        if match and line[match.end()].isupper():
            return pattern.sub(replacement, line, count=1), 1
    return line, 0


def remove_gazette_markings(text: str) -> tuple[str, dict[str, int]]:
    """Remove Công báo headers/footers and page numbers directly attached to them.

    Handles layouts such as:
    - ``18 CÔNG BÁO/Số 681 + 682/Ngày 16-7-2014``
    - ``16\nCÔNG BÁO/Số 681 + 682/Ngày 16-7-2014``
    - ``CÔNG BÁO/Số 681 + 682/Ngày 16-7-2014 16``

    A standalone number is removed only when it is directly adjacent to a
    Công báo marker, so ordinary numbers in legal text are preserved.
    """
    counts = {"gazette_markings": 0, "page_counters": 0}
    lines = text.splitlines()
    cleaned_lines: list[str] = []
    skip_next_standalone_number = False

    for original_line in lines:
        line = original_line
        marker = GAZETTE_MARKER_RE.search(line)

        if marker:
            counts["gazette_markings"] += 1
            prefix = line[:marker.start()].strip()

            # A number before the marker on the same line is a page counter
            # only if it is the entire prefix (e.g. "18 CÔNG BÁO/SỐ ...").
            if not prefix or STANDALONE_NUMBER_RE.fullmatch(prefix):
                if prefix:
                    counts["page_counters"] += 1
                if cleaned_lines and STANDALONE_NUMBER_RE.fullmatch(cleaned_lines[-1].strip()):
                    cleaned_lines.pop()
                    counts["page_counters"] += 1
                skip_next_standalone_number = True
                continue

            # Keep legal text before the marker; discard the marker and suffix.
            line = prefix
        else:
            stripped = line.strip()
            if skip_next_standalone_number:
                skip_next_standalone_number = False
                if STANDALONE_NUMBER_RE.fullmatch(stripped):
                    counts["page_counters"] += 1
                    continue

        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    return normalize_extracted_text("\n".join(cleaned_lines)), counts


def clean_extracted_text(text: str) -> tuple[str, dict[str, int]]:
    """Remove Công báo markings, URLs, export timestamps, and page counters."""
    text, gazette_counts = remove_gazette_markings(text)

    # NFC first, then normalize old Vietnamese tone placement without changing punctuation.
    text = unicodedata.normalize("NFC", text)
    text, tone_changes = normalize_vietnamese_tone_placement(text)
    counts = {
        "urls": 0,
        "timestamps": 0,
        "page_counters": gazette_counts["page_counters"],
        "gazette_markings": gazette_counts["gazette_markings"],
        "tone_placement_changes": tone_changes,
        "label_fixes": 0,
    }
    cleaned_lines: list[str] = []

    for line in text.splitlines():
        line, n_urls = URL_RE.subn(" ", line)
        counts["urls"] += n_urls

        line, n_timestamps = TIMESTAMP_RE.subn(" ", line)
        counts["timestamps"] += n_timestamps

        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        if not line:
            continue

        if (
            PAGE_COUNTER_RE.fullmatch(line)
            or SINGLE_PAGE_LABEL_RE.fullmatch(line)
            or STANDALONE_NUMBER_RE.fullmatch(line)
        ):
            counts["page_counters"] += 1
            continue

        line, n_labels = normalize_label_punctuation(line)
        counts["label_fixes"] += n_labels
        cleaned_lines.append(line)

    cleaned = normalize_extracted_text("\n".join(cleaned_lines))
    return cleaned, counts


def qwen_transcribe_page(page: pymupdf.Page, page_number: int, pdf_stem: str) -> str:
    """Render a page and transcribe it with Qwen3-VL; save failed page images."""
    import ollama
    import pymupdf

    scale = RENDER_DPI / 72
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)

    if pix.width <= 0 or pix.height <= 0 or len(pix.samples) == 0:
        logger.error(
            "Ảnh render không hợp lệ: file=%s, trang=%d, kích thước=%sx%s",
            pdf_stem, page_number, pix.width, pix.height,
        )
        return ""

    image_bytes = pix.tobytes("png")
    last_error: Optional[Exception] = None

    # One initial attempt plus OCR_RETRIES retries.
    for attempt in range(OCR_RETRIES + 1):
        try:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Đây là trang {page_number} của một văn bản pháp luật.\n\n"
                            f"{OCR_PROMPT}"
                        ),
                        "images": [image_bytes],
                    }
                ],
                options={"temperature": 0},
                keep_alive=OLLAMA_KEEP_ALIVE,
            )

            raw_content = response.message.content or ""
            text = normalize_extracted_text(raw_content)

            if text:
                if attempt > 0:
                    logger.info(
                        "OCR thành công sau lần thử lại: file=%s, trang=%d, lần=%d",
                        pdf_stem, page_number, attempt + 1,
                    )
                return text

            logger.warning(
                "Qwen3-VL trả về content rỗng: file=%s, trang=%d, lần=%d/%d, "
                "response_keys=%s, raw_content=%r",
                pdf_stem, page_number, attempt + 1, OCR_RETRIES + 1,
                list(response.model_dump().keys()), raw_content,
            )
        except Exception as exc:
            last_error = exc
            logger.exception(
                "Gọi Qwen3-VL lỗi: file=%s, trang=%d, lần=%d/%d: %s",
                pdf_stem, page_number, attempt + 1, OCR_RETRIES + 1, exc,
            )

    # Preserve the rendered page so it can be inspected or OCR'd manually.
    FAILED_OCR_DIR.mkdir(parents=True, exist_ok=True)
    image_path = FAILED_OCR_DIR / f"{pdf_stem}_page_{page_number:03d}.png"
    try:
        image_path.write_bytes(image_bytes)
        logger.error(
            "OCR thất bại sau %d lần; đã lưu ảnh trang để kiểm tra: %s",
            OCR_RETRIES + 1, image_path,
        )
    except Exception:
        logger.exception("Không lưu được ảnh trang lỗi: %s", image_path)

    if last_error is not None:
        logger.error(
            "Lỗi cuối cùng khi OCR file=%s, trang=%d: %s",
            pdf_stem, page_number, last_error,
        )
    return ""


def page_has_images(page: pymupdf.Page) -> bool:
    """Detect image blocks actually shown on the page."""
    try:
        blocks = page.get_text("dict").get("blocks", [])
        return any(block.get("type") == 1 for block in blocks)
    except Exception:
        # Conservative fallback: don't force OCR unless text is also sparse.
        return False


def process_page(page: pymupdf.Page, page_number: int, pdf_stem: str) -> tuple[str, str]:
    """Return extracted text and extraction method; cleaning happens after extraction.

    Prefer native PDF text whenever it is substantial. A page may contain a logo,
    seal, or other image while still having selectable text; presence of any image
    alone must not cause native text to be discarded in favor of OCR.
    """
    native_text = normalize_extracted_text(page.get_text("text", sort=True))

    # Native text is the most faithful source for text-based PDFs. Only OCR pages
    # where native extraction is empty/sparse, rather than OCR'ing every page that
    # contains any image object.
    if len(native_text) >= MIN_TEXT_CHARS:
        return native_text, "pymupdf"

    contains_images = page_has_images(page)
    if contains_images or native_text:
        try:
            ocr_text = qwen_transcribe_page(page, page_number, pdf_stem)
            if ocr_text:
                return ocr_text, "qwen3-vl"
            logger.warning(
                "Trang %d OCR trả về rỗng; dùng text trích xuất gốc (native_chars=%d).",
                page_number, len(native_text)
            )
        except Exception as exc:
            logger.exception("OCR lỗi ở trang %d: %s", page_number, exc)

    if native_text:
        return native_text, "pymupdf"
    return "", "empty"


def process_pdf(pdf_path: Path, raw_output_path: Path, clean_output_path: Path) -> bool:
    """Extract PDF, save raw TXT, then clean and save the parser-ready TXT in parser/cleaned_texts."""
    started = time.perf_counter()
    logger.info("Đang xử lý: %s", pdf_path)
    import pymupdf

    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        logger.exception("Không mở được PDF: %s", pdf_path)
        return False

    page_texts: list[str] = []
    methods: dict[str, int] = {"pymupdf": 0, "qwen3-vl": 0, "empty": 0}

    try:
        for index, page in enumerate(doc):
            text, method = process_page(page, index + 1, pdf_path.stem)
            methods[method] += 1

            # Preserve page boundaries for debugging and downstream parsing.
            if text:
                page_texts.append(f"\n\n{text}\n\n")
            else:
                marker = f"[TRANG {index + 1} KHÔNG TRÍCH XUẤT ĐƯỢC]"
                page_texts.append(f"\n\n{marker}\n\n")
                logger.warning("Trang %d không trích xuất được nội dung.", index + 1)
    finally:
        doc.close()

    raw_text = normalize_extracted_text("".join(page_texts))
    if not raw_text:
        logger.error("Không có nội dung để ghi: %s", pdf_path)
        return False

    raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Save the extracted version first, before removing any suspected noise.
        raw_output_path.write_text(raw_text + "\n", encoding="utf-8")
    except Exception:
        logger.exception("Không ghi được file trích xuất thô: %s", raw_output_path)
        return False

    clean_text, removed = clean_extracted_text(raw_text)
    if not clean_text:
        logger.error("Văn bản rỗng sau làm sạch; giữ bản thô tại: %s", raw_output_path)
        return False

    try:
        clean_output_path.write_text(clean_text + "\n", encoding="utf-8")
    except Exception:
        logger.exception("Không ghi được file đã làm sạch: %s", clean_output_path)
        return False

    elapsed = time.perf_counter() - started
    logger.info(
        "Hoàn tất: %s | trang=%d | PyMuPDF=%d | Qwen3-VL=%d | rỗng=%d "
        "| URL bỏ=%d | timestamp bỏ=%d | số trang bỏ=%d | marking Công báo bỏ=%d "
        "| dấu thanh chuẩn hóa=%d | %.1fs",
        clean_output_path.name,
        sum(methods.values()),
        methods["pymupdf"],
        methods["qwen3-vl"],
        methods["empty"],
        removed["urls"],
        removed["timestamps"],
        removed["page_counters"],
        removed["gazette_markings"],
        removed["tone_placement_changes"],
        elapsed,
    )
    return methods["empty"] == 0



def clean_existing_texts() -> dict[str, int]:
    """Re-clean existing extracted TXT files without reopening PDFs or running OCR.

    Reads parser/extracted_texts_qwen/*.txt and overwrites the corresponding
    parser/cleaned_texts/*.txt using the current clean_extracted_text() logic.
    """
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(
        (path for path in RAW_OUTPUT_DIR.glob("*.txt") if path.is_file()),
        key=lambda path: path.name.lower(),
    )

    succeeded = 0
    failed = 0
    totals = {
        "urls": 0,
        "timestamps": 0,
        "page_counters": 0,
        "gazette_markings": 0,
        "tone_placement_changes": 0,
        "label_fixes": 0,
    }

    if not raw_files:
        logger.warning("Không tìm thấy TXT thô trong %s", RAW_OUTPUT_DIR)
        return {"succeeded": 0, "failed": 0, "total": 0, **totals}

    logger.info("Tìm thấy %d TXT thô; chỉ chạy bước clean, không trích xuất PDF/OCR.", len(raw_files))
    for raw_path in raw_files:
        clean_path = OUTPUT_DIR / raw_path.name
        try:
            raw_text = raw_path.read_text(encoding="utf-8")
            cleaned_text, removed = clean_extracted_text(raw_text)
            if not cleaned_text.strip():
                logger.error("Clean TXT rỗng; giữ nguyên file đích nếu có: %s", raw_path.name)
                failed += 1
                continue
            clean_path.write_text(cleaned_text + "\n", encoding="utf-8")
            succeeded += 1
            for key in totals:
                totals[key] += removed.get(key, 0)
            logger.info(
                "Clean lại %s | số trang bỏ=%d | marking Công báo bỏ=%d | "
                "dấu thanh chuẩn hóa=%d | nhãn sửa=%d | URL bỏ=%d | timestamp bỏ=%d",
                raw_path.name,
                removed.get("page_counters", 0),
                removed.get("gazette_markings", 0),
                removed.get("tone_placement_changes", 0),
                removed.get("label_fixes", 0),
                removed.get("urls", 0),
                removed.get("timestamps", 0),
            )
        except Exception:
            logger.exception("Không clean được TXT: %s", raw_path)
            failed += 1

    logger.info(
        "Hoàn tất clean lại TXT: thành công=%d | lỗi=%d | tổng=%d | "
        "số trang bỏ=%d | dấu thanh chuẩn hóa=%d",
        succeeded, failed, len(raw_files), totals["page_counters"], totals["tone_placement_changes"],
    )
    return {"succeeded": succeeded, "failed": failed, "total": len(raw_files), **totals}

def discover_pdfs() -> list[Path]:
    """Find PDFs under data/raw_data/circulars and laws_and_decrees."""
    pdfs: list[Path] = []
    for folder_name in SUB_FOLDERS:
        folder = RAW_DATA_DIR / folder_name
        if not folder.exists():
            logger.warning("Không tìm thấy thư mục: %s", folder)
            continue
        pdfs.extend(path for path in folder.rglob("*.pdf") if path.is_file())
        pdfs.extend(path for path in folder.rglob("*.PDF") if path.is_file())
    return sorted(set(pdfs), key=lambda path: str(path).lower())


def run_cleaner() -> dict[str, int]:
    """Process PDFs and return a summary; can be imported and called by other modules."""
    RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_files = discover_pdfs()

    if not pdf_files:
        logger.warning("Không tìm thấy PDF trong %s", RAW_DATA_DIR)
        return {"succeeded": 0, "skipped": 0, "failed": 0, "total": 0}

    logger.info("Tìm thấy %d file PDF.", len(pdf_files))
    succeeded = 0
    skipped = 0
    failed = 0

    for pdf_path in pdf_files:
        # Keep existing output naming so the parser can read the final output from cleaned_texts.
        raw_output_path = RAW_OUTPUT_DIR / f"{pdf_path.stem}.txt"
        clean_output_path = OUTPUT_DIR / f"{pdf_path.stem}.txt"

        if (
            SKIP_EXISTING_OUTPUTS
            and clean_output_path.exists()
            and clean_output_path.stat().st_size > 0
            and raw_output_path.exists()
            and raw_output_path.stat().st_size > 0
        ):
            logger.info("Bỏ qua file đã có cả bản thô và bản sạch: %s", pdf_path.name)
            skipped += 1
            continue

        if process_pdf(pdf_path, raw_output_path, clean_output_path):
            succeeded += 1
        else:
            failed += 1

    logger.info(
        "Kết quả: thành công=%d | bỏ qua=%d | cần kiểm tra=%d",
        succeeded,
        skipped,
        failed,
    )
    return {
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "total": len(pdf_files),
    }


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Trích xuất PDF và làm sạch văn bản pháp luật.")
    cli.add_argument(
        "--clean-existing",
        action="store_true",
        help="Chỉ làm sạch lại TXT đã có trong extracted_texts_qwen; không mở PDF hoặc chạy OCR.",
    )
    args = cli.parse_args()
    if args.clean_existing:
        clean_existing_texts()
    else:
        run_cleaner()
