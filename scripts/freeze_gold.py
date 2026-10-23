"""Freeze evaluation labels in the Test split only when final checks pass."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from validate_benchmark import DATA,ROOT,check,load
MANIFEST=ROOT/'docs'/'test_gold_freeze.json'

def sha256(data):return hashlib.sha256(data).hexdigest()
def payload():
    test=load(DATA/'queries_test.json');g=load(DATA/'ground_truth.json')
    by_id={x['id']:x for x in g}
    return {'questions':test,'test_ground_truth':[by_id[q['id']] for q in test]}
def current():
    blob=json.dumps(payload(),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8')
    return {'scope':'TEST_QUESTIONS_AND_GOLD','test_question_count':len(payload()['questions']),
            'sha256':sha256(blob), 'note':'Freeze sau khi schema FINAL PASS; không sửa đáp án Test trong quá trình thử hệ thống.'}
def run(mode):
    if mode=='create':
        problems,*_=check(final=True)
        if problems:raise RuntimeError(f'Chưa thể khóa đáp án Test: {len(problems)} lỗi nghiệm thu, ví dụ {problems[:3]}')
        if MANIFEST.exists():raise RuntimeError('Manifest đáp án Test đã tồn tại')
        MANIFEST.write_text(json.dumps(current(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('FROZEN: cả câu hỏi và đáp án Test')
    else:
        if not MANIFEST.exists():raise RuntimeError('Chưa có manifest Test Gold vì chưa đủ chunks/review')
        if current()!=load(MANIFEST):raise RuntimeError('Test Gold bị thay đổi')
        print('PASS: Test Gold không đổi')
if __name__=='__main__':
    p=argparse.ArgumentParser();gr=p.add_mutually_exclusive_group(required=True)
    gr.add_argument('--create',action='store_true');gr.add_argument('--verify',action='store_true')
    a=p.parse_args()
    try:run('create' if a.create else 'verify')
    except RuntimeError as exc:print('FAIL:',exc);sys.exit(1)
