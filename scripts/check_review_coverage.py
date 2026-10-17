"""Check all question review sheet coverage; does not set gold flags."""
import argparse,csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def readcsv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--test-review-sheet',type=Path,default=None,help='File review Test RIÊNG từ gói riêng; không đẩy repo chung')
    args=ap.parse_args()
    dev=json.loads((ROOT/'data/benchmark/queries_dev.json').read_text(encoding='utf8'))
    test=json.loads((ROOT/'data/benchmark/queries_test.json').read_text(encoding='utf8'))
    x=readcsv(ROOT/'docs/review_dev_285.csv')
    source=args.test_review_sheet or ROOT/'docs/review_test_15_RESTRICTED.csv'
    y=readcsv(source) if source.is_file() else None
    assert [r['question_id'] for r in x]==[q['id'] for q in dev]
    if y is not None: assert [r['question_id'] for r in y]==[q['id'] for q in test]
    reviewed=lambda rows:sum(bool(r['reviewer'].strip() and r['reviewed_at'].strip() and r['valid_at_question_date'].strip()) for r in rows)
    print(f'Dev review rows: {len(x)}, completed forms: {reviewed(x)}')
    if y is None:
        print(f'Test review: file RESTRICTED không có trong gói Git (đúng); nhận {len(test)} câu Test khóa, truyền --test-review-sheet để soát bảng riêng.')
    else: print(f'Test review rows: {len(y)}, completed forms: {reviewed(y)}')
    print('Note: completed spreadsheet fields do not automatically approve legal correctness.')
