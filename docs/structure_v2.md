# Article / appendix / footer separation — structure v2

The prior corpus treated appendix list items as clauses of ND01 Article 67 and
ND04 Article 26. This changed their apparent meaning and attached form/customs
text to unrelated legal articles. The corrected corpus is under
`data/structure_v2`; all earlier benchmark files and scores remain unchanged.

## Changes

- `parser/document_sections.py` partitions terminal signatures/recipients and
  appendix headings before article/clause parsing. Exact text offsets are kept;
  concatenating the sections reconstructs the extracted source text.
- `parser/parser.py` preserves ancillary sections in document output. Ordinary
  appendix references and quoted signature strings do not trigger separation.
- The two contaminated final articles are rebuilt from page-aware PDF text;
  previous articles and verified metadata are retained. ND01's boundary is PDF
  page 31 (printed page 33); ND04's is PDF page 13.
- ND04's source reference **Khoản 5 Điều 3** is restored from the PDF. Its digit
  was missing in the earlier parsed export. Recognizable page headers/browser
  lines are excluded from the rebuilt article; raw text remains archived.
- Both final articles contain unnumbered paragraphs. Their internal clause IDs
  are synthetic and flagged as such. Chunk text uses **Nội dung điều**, so the
  storage identifier is not presented as an actual numbered legal clause.
- Footers and complete appendices remain in document ancillary sections and
  `source_archives/ND01.json`, `source_archives/ND04.json`, with source PDF hashes,
  page provenance, extraction versions and exact source-text partitions. They
  are excluded from this article-only retrieval corpus. A future appendix/form
  retrieval path must retain the heading and interpretation context.

## Output and validation

| Measure | Frozen baseline | Structure v2 |
|---|---:|---:|
| Articles | 398 | 398 |
| Clauses (including internal synthetic units) | 986 | 971 |
| Raw article chunks | 1,066 | 1,021 |
| BKAI token-safe chunks | 1,079 | 1,024 |

The 50 question labels are migrated only after checking that their evidence text
is identical (all current question evidence is in L01). The three earlier Dev
query clarifications are retained. Human review and exhaustive relevance labeling
remain pending. IDs in the corrected final articles may have different content;
other labels must not be migrated by ID alone.

The final BKAI corpus has **zero inputs above 256 tokens**, maximum **256**.
Audit: `data/structure_v2/embedding/bkai_token_audit.json`.
Fixture SHA-256: `882ccfe5db1a061d5f133759cf67a16428608a6e5fb2e99379efe6be0a9ee78f`.
All seven documents pass the existing ID/parent/content reconstruction validator.
Six new boundary/real-document tests and the existing tests pass: **16 Python
tests + 4 Node tests**. Repeated raw exports have identical fixture hashes.

## Rebuild

Use Python with the parser dependencies (`pdfplumber`, Pydantic 2) installed,
as described in `parser/README.md`. The embedding environment additionally needs
the embedding/BKAI requirements. The extraction versions used locally are recorded
inside the source archives; changing extraction dependencies can change output.

```powershell
python parser/export_structure_v2.py
$env:HF_HOME = "$PWD\.venv-embedding\hf-cache"
.\.venv-embedding\Scripts\python.exe embedding/fit_token_budget.py --input data/structure_v2/embedding/priority_chunks.json --output-dir data/structure_v2/embedding --dataset-name structure_v2_bkai_token_safe
.\.venv-embedding\Scripts\python.exe embedding/audit_token_limits.py --chunks data/structure_v2/embedding/priority_bkai_chunks.json --output data/structure_v2/embedding/bkai_token_audit.json
python -m unittest discover -s test -p 'test_*.py'
node --test test/priority_dataset.test.cjs
```

## Remaining scope

This repairs the two identified final articles, not every extraction issue in the
corpus. ND01's article-level validity and ND03's status still require verification.
The current expiry filter leaves 630 eligible chunks in the new token-safe corpus;
partially expired/unknown-status documents remain included. The old three-model
scores are not scores for v2: rerun Dev on the new fixture and matching labels
before comparing quality. The Test split has not been evaluated.
