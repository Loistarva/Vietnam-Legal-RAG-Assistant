"""Freeze ONLY the Test questions, so context IDs can be added later without changing test split."""
import argparse, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'data'/'benchmark'/'queries_test.json'
MANIFEST=ROOT/'docs'/'test_questions_freeze.json'

def sha256(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def manifest():
    q=json.loads(Q.read_text(encoding='utf8'))
    return {'scope':'TEST_QUERIES_ONLY_NOT_GOLD_ANSWERS','frozen_file':'data/benchmark/queries_test.json',
            'sha256':sha256(Q),'question_count':len(q),'test_ids':[r['id'] for r in q],
            'note':'Các đáp án gold_context_ids vẫn cần đối chiếu sau khi index chunk.'}

def run(mode):
    current=manifest()
    if mode=='create':
        if MANIFEST.exists():
            raise RuntimeError('Đã tồn tại manifest; không ghi đè bản freeze hiện có')
        MANIFEST.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('FROZEN: câu hỏi Test, không bao gồm ground_truth')
    else:
        if not MANIFEST.exists():raise RuntimeError('Chưa có manifest')
        existing=json.loads(MANIFEST.read_text(encoding='utf8'))
        if existing!=current:raise RuntimeError('Test đã thay đổi: hash hoặc danh sách ID không trùng')
        print('PASS: 15 câu Test chưa bị thay đổi')

if __name__=='__main__':
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--create',action='store_true');group.add_argument('--verify',action='store_true');a=p.parse_args()
    try:run('create' if a.create else 'verify')
    except RuntimeError as e:print('FAIL:',e);sys.exit(1)
