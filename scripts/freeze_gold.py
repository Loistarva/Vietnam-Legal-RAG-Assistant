"""Freeze evaluation labels in the Test split only when final checks pass on Test questions."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT/'scripts'))

from validate_benchmark import DATA, REF, canonical_json_sha256, check, inputs, load
MANIFEST=ROOT/'docs'/'test_gold_freeze.json'

def sha256(data):
    if isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(data).hexdigest()
    return canonical_json_sha256(data)

def payload():
    test=load(DATA/'queries_test.json');g=load(DATA/'ground_truth.json')
    by_id={x['id']:x for x in g}
    return {'questions':test,'test_ground_truth':[by_id[q['id']] for q in test]}

def verify_test_split_ready() -> list[str]:
    dev, test, gt, articles, chunks, docs, schema = inputs()
    chunk_index = {c['chunk_id']: c for c in chunks}
    by_id = {x['id']: x for x in gt}
    issues: list[str] = []
    if not test:
        issues.append('Tập Test rỗng')
    for q in test:
        qid = q.get('id')
        if q.get('split') != 'test':
            issues.append(f'{qid}: query trong queries_test.json có split != "test"')
        g = by_id.get(qid)
        if not g:
            issues.append(f'{qid}: thiếu bản ghi trong ground_truth.json')
            continue
        if g.get('split') and g.get('split') != 'test':
            issues.append(f'{qid}: ground_truth có split != "test"')
        if g.get('answer_kind') != 'reviewed_answer':
            issues.append(f'{qid}: answer chưa được biên soạn và duyệt thành câu trả lời trực tiếp')
        if g.get('review_status') not in ('source_checked', 'peer_reviewed', 'lawyer_verified') or not g.get('verified_by') or not g.get('verified_at'):
            issues.append(f'{qid}: chưa có xác minh pháp lý kèm người/ngày')
        if g.get('evidence_level') != 'full_text_checked':
            issues.append(f'{qid}: chứng cứ pháp lý chưa được đối chiếu toàn văn')
        if not g.get('gold_clause_ids'):
            issues.append(f'{qid}: chưa có gold_clause_ids')
        if not g.get('gold_context_ids'):
            issues.append(f'{qid}: chưa có gold_context_ids')
        if not g.get('gold_context_ids_confirmed'):
            issues.append(f'{qid}: chưa xác nhận chunk IDs trong index')
        if g.get('mapping_status') != 'production_verified':
            issues.append(f'{qid}: chưa production_verified')
        for cid in g.get('gold_context_ids', []):
            pr = chunk_index.get(cid)
            if not pr:
                issues.append(f'{qid}: gold ID không tồn tại trong production index: {cid}')
            elif g.get('gold_article_ids') and pr.get('article_id') not in g['gold_article_ids']:
                issues.append(f'{qid}: gold ID {cid} sai Điều trong production index')
    return issues

def current():
    pl = payload()
    return {
        'scope': 'TEST_QUESTIONS_AND_GOLD',
        'test_question_count': len(pl['questions']),
        'test_ids': [q['id'] for q in pl['questions']],
        'sha256': canonical_json_sha256(pl),
        'note': 'Freeze sau khi kiểm định đầy đủ (full_text_checked / source_checked) trên tập Test; không sửa đáp án Test trong quá trình thử hệ thống.'
    }

def run(mode, force=False):
    if mode=='create':
        test_issues = verify_test_split_ready()
        if test_issues:
            raise RuntimeError(f'Chưa thể khóa đáp án Test: {len(test_issues)} lỗi nghiệm thu trên tập Test, ví dụ {test_issues[:3]}')

        problems, *_ = check(final=False)
        candidate = current()
        existing = load(MANIFEST) if MANIFEST.exists() else None
        manifest_changed = existing is not None and existing != candidate
        if manifest_changed:
            # The validator correctly reports that the old freeze no longer matches.
            # Compare it below, while keeping every other structural issue fatal.
            problems = [problem for problem in problems
                        if problem != 'Gold Test đã thay đổi so với manifest khóa SHA-256']
        if problems:
            raise RuntimeError(f'Lỗi cấu trúc benchmark trước khi tạo manifest: {problems[:3]}')
        if existing == candidate:
            print(f'PASS: manifest Test Gold đã khớp sau khi kiểm tra lại ({candidate["test_question_count"]} câu)')
            return
        if manifest_changed and not force:
            raise RuntimeError('Manifest Test Gold đã tồn tại và khác nội dung; dùng --force nếu chủ đích thay freeze')
        MANIFEST.write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(
            f'FROZEN: cả câu hỏi và đáp án Test '
            f'({candidate["test_question_count"]} câu)'
        )

    else:
        if not MANIFEST.exists():raise RuntimeError('Chưa có manifest Test Gold vì chưa đủ chunks/review')
        test_issues = verify_test_split_ready()
        if test_issues:
            raise RuntimeError(f'Tập Test không đạt chuẩn final: {test_issues[:3]}')
        if current()!=load(MANIFEST):raise RuntimeError('Test Gold bị thay đổi')
        print(f'PASS: Test Gold ({len(payload()["questions"])} câu) không đổi')

if __name__=='__main__':
    p=argparse.ArgumentParser();gr=p.add_mutually_exclusive_group(required=True)
    gr.add_argument('--create',action='store_true');gr.add_argument('--verify',action='store_true')
    p.add_argument('--force',action='store_true',help='Cho phép thay manifest hiện hữu khi hash/list ID khác')
    a=p.parse_args()
    try:run('create' if a.create else 'verify', force=a.force)
    except RuntimeError as exc:print('FAIL:',exc);sys.exit(1)
