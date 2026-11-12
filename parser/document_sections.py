"""Conservative document-tail boundaries with exact source-text offsets.

No text is discarded: body + footer + appendix reconstruct the input exactly.
Appendices are not assigned Article/Clause IDs or included in article-only retrieval.
"""
import re


def partition_document(text: str) -> list[dict]:
    # A heading must be on its own line, or have a known all-capitals title.
    # Ordinary references such as 'theo Phụ lục của Nghị định' are not headings.
    candidates = re.finditer(
        r'(?m)^[ \t]*(?:Phụ lục|PHỤ LỤC)[ \t]*(?=\r?$|\s+(?:DANH MỤC|MẪU))'
        r'|(?<!\S)(?:Phụ lục|PHỤ LỤC)\s+(?=DANH MỤC|MẪU)', text)
    appendix_start = len(text)
    for candidate in candidates:
        line_start = text.rfind('\n', 0, candidate.start()) + 1
        is_heading_line = not text[line_start:candidate.start()].strip()
        if is_heading_line or './.' in text[:candidate.start()]:
            appendix_start = candidate.start()
            break
    before_appendix = text[:appendix_start]
    # Only a terminal signature after the closing punctuation is a footer.
    closing = list(re.finditer(r'\./\.', before_appendix))
    footer_start = appendix_start
    if closing:
        terminal = closing[-1].end()
        signature = re.match(r'\s*(Nơi nhận\s*:|TM\.\s*CHÍNH PHỦ|KT\.\s*THỦ TƯỚNG)',
                              before_appendix[terminal:])
        if signature and not re.match(r'\s*[”"»’]', before_appendix[terminal + signature.end():]):
            footer_start = terminal + signature.start(1)
    ranges = [('body', 0, footer_start),
              ('footer', footer_start, appendix_start),
              ('appendix', appendix_start, len(text))]
    sections = [{'section_type': kind, 'start': start, 'end': end,
                 'text': text[start:end], 'retrieval_eligible': kind == 'body'}
                for kind, start, end in ranges if end > start]
    if ''.join(section['text'] for section in sections) != text:
        raise ValueError('Document section reconstruction failed')
    return sections
