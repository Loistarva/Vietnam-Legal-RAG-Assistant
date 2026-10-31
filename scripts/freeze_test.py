"""Freeze ONLY the Test questions using canonical JSON SHA-256."""
import argparse, hashlib, json, sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT=Path(__file__).resolve().parents[1]
Q=ROOT/'data'/'benchmark'/'queries_test.json'
MANIFEST=ROOT/'docs'/'test_questions_freeze.json'

def sha256_canonical(obj):
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).replace('\r\n', '\n') + '\n'
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()

def sha256(p):
    obj = json.loads(Path(p).read_text(encoding='utf-8'))
    return sha256_canonical(obj)

def manifest():
    q=json.loads(Q.read_text(encoding='utf8'))
    return {'scope':'TEST_QUERIES_ONLY_NOT_GOLD_ANSWERS','frozen_file':'data/benchmark/queries_test.json',
            'sha256':sha256_canonical(q),'question_count':len(q),'test_ids':[r['id'] for r in q],
            'note':'Các câu hỏi Test đã được phân tầng theo nhóm Khoản (seed=42) và khóa SHA-256 trên JSON chuẩn hóa.'}

def run(mode, force=False):
    current=manifest()
    if mode=='create':
        if MANIFEST.exists() and not force:
            raise RuntimeError('Đã tồn tại manifest; chỉ đóng băng lại với --force và ghi lý do vào docs/sprint6_benchmark.md mục 6')
        MANIFEST.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(f'FROZEN: {current["question_count"]} câu hỏi Test (sha256={current["sha256"]})')
    else:
        if not MANIFEST.exists():raise RuntimeError('Chưa có manifest')
        existing=json.loads(MANIFEST.read_text(encoding='utf8'))
        if existing!=current:raise RuntimeError('Test đã thay đổi: hash hoặc danh sách ID không trùng')
        print(f'PASS: {current["question_count"]} câu Test chưa bị thay đổi')

if __name__=='__main__':
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--create',action='store_true');group.add_argument('--verify',action='store_true')
    p.add_argument('--force',action='store_true')
    a=p.parse_args()
    try:run('create' if a.create else 'verify', force=a.force)
    except RuntimeError as e:print('FAIL:',e);sys.exit(1)
