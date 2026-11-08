# D1.2 — bàn giao citation validator

Triển khai trên `feature/week09-dev1-planning`, ngày 07/11/2026.
Schema và generation được lấy nguyên bản từ Dev 3, commit
`d94eeec` (`feature/contracts-prompt-gateway`); không tạo schema song song,
không sửa mã Dev 3 hay tự coi prompt là đã được Freeze M1.

## Giao diện cho Dev 5

```python
from generation.prompt_builder import map_evidence_indices_to_citations
from grounding.citation_validator import validate_citations

# context phải chính là payload đã render vào prompt, sau chọn/truncate evidence.
citations, invalid = map_evidence_indices_to_citations(llm.evidence_indices, context)
result = validate_citations(
    context, citations,
    evidence_indices=llm.evidence_indices,
    invalid_indices=invalid,
)
```

Payload minh họa (ID giả để test contract, không phải căn cứ pháp lý):

```python
from schemas.models import ContextPayload, EvidenceItem

context = ContextPayload(
    query_id="demo", query="Câu hỏi minh họa", as_of_date="2026-11-07",
    evidence_items=[EvidenceItem(
        evidence_index=1, chunk_id="child-1", parent_clause_id="parent-1",
        document_id="doc-1", article_id="article-1", clause_id="clause-1",
        content="Nội dung evidence đã chọn", validity_status="valid",
    )],
)
citations, invalid = map_evidence_indices_to_citations([1], context)
assert validate_citations(
    context, citations, evidence_indices=[1], invalid_indices=invalid,
).grounding_status == "PASS"
```

Caller dùng model canonical từ `schemas.models`, giữ toàn bộ indices gốc và lỗi
mapper; không lọc lỗi để tạo PASS. Khi dữ liệu thô không parse được schema,
Gate phải chặn/abstain trước khi gọi validator. Không dùng `model_construct`
hoặc ép kiểu raw output để bỏ qua validation. Hàm không sửa payload đầu vào.

PASS yêu cầu tập indices và citations khớp nhau, mỗi index duy nhất trong 1..5,
evidence tồn tại trong selected context, và cả năm trường `chunk_id`,
`document_id`, `article_id`, `clause_id`, `parent_clause_id` khớp giữa citation,
evidence và source_map. Có thể chỉ cite một phần evidence, không bắt buộc cite
toàn bộ context. Parent mở rộng vẫn giữ chunk ID/provenance do producer cung cấp;
không thay chunk ID bằng parent ID, không suy diễn quan hệ bằng cách cắt chuỗi.
Producer chịu trách nhiệm bảo đảm content thực sự đúng nguồn và đúng phần đã
đưa vào prompt; validator không thể xác minh điều này từ ID đơn thuần.

## Chính sách bảo thủ và reason codes

Context hoặc citation rỗng trả FAIL (`EMPTY_CONTEXT` / `MISSING_CITATIONS`).
Validator chỉ trả PASS/FAIL; Gate quyết định ABSTAIN/NEEDS_CLARIFICATION, buffer
answer đến khi kiểm tra xong và không phát answer pháp lý khi FAIL. Các trường
abstained/needs_clarification của LLM không tự động biến citation thiếu thành PASS.
Chính sách này cần Dev 3 + Dev 5 review khi tích hợp; chưa xác nhận thay họ.

Reason có thứ tự ưu tiên cố định trong code: invalid input type, mapper error,
raw index, context, source_map, missing citations, citation indices, provenance.
Một lần gọi trả lỗi đầu tiên; `valid_citations` rỗng khi FAIL, không trả PASS
một phần. `invalid_indices` chỉ chứa số nguyên, sắp tăng, loại trùng.

Các nhóm reason: `INVALID_CONTEXT_TYPE`, `INVALID_CITATION_TYPE`,
`MAPPER_INVALID_INDICES`, `INVALID_MAPPER_RESULT`, `INVALID_EVIDENCE_INDEX`, `DUPLICATE_EVIDENCE_INDEX`,
`EMPTY_CONTEXT`, `TOO_MANY_EVIDENCE_ITEMS`, `INVALID_CONTEXT_INDEX`,
`DUPLICATE_CONTEXT_INDEX`, `INVALID_CONTEXT_EVIDENCE`, `EMPTY_EVIDENCE_FIELD`, `SOURCE_MAP_INDEX_MISMATCH`,
`SOURCE_MAP_PROVENANCE_MISMATCH`, `MISSING_CITATIONS`, `INVALID_CITATION_INDEX`,
`DUPLICATE_CITATION_INDEX`, `CITATION_INDEX_SET_MISMATCH`,
`CITATION_OUTSIDE_CONTEXT`, `CITATION_PROVENANCE_MISMATCH`.
PASS reason: `CITATIONS_MATCH_SELECTED_CONTEXT`.

Đây là kiểm tra provenance, không chứng minh Legal Correctness, Context
Faithfulness hoặc hiệu lực pháp luật. `unsupported_claims` không được suy diễn.
Không thay Grounding Gate của Dev 5 và không thay đổi Test/Gold/corpus.

## Kiểm tra và review

```powershell
python -m pytest test/grounding/test_citation_validator.py -q
python -m pytest -q
git diff --check
```

Tests gồm mapper thực của Dev 3, sai từng trường provenance, parent/chunk nhầm,
source_map giả/mất/thừa index, context/citation rỗng, index sai kiểu/phạm vi,
mapping bị bỏ sót, duplicates, không mutation và PASS với subset selected evidence.
Trạng thái: implementation hoàn thành; chờ Dev 3 + Dev 5 peer review/tích hợp Gate.

Rà soát cuối bổ sung kiểm tra container sai kiểu/None và model bị mutate sau parse,
tránh exception thay vì FAIL. Kết quả cuối: 67 tests D1.2 PASS; full pytest
915 passed, 1 skipped (69.13s); 8 tests Node evidence guard PASS;
`git diff --check` sạch. Chưa chạy CI remote/chưa commit hoặc push.

## Giới hạn citation cấp Điểm

Validator hiện kiểm đến document/article/clause và selected evidence. Citation cấp Điểm chưa được kiểm độc lập; không suy ra một Điểm là đúng chỉ vì Khoản chứa nó khớp. Reviewer Dev 3 + Dev 5 chốt contract Điểm trước khi mở rộng.
