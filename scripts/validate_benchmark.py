"""Benchmark validations. Default = handoff structure only, --final requires reviewed direct answers and verified production gold."""
from __future__ import annotations
import argparse, datetime, json, re, sys, hashlib
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'benchmark'
REF=ROOT/'data'/'reference'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def inputs():
    return (load(DATA/'queries_dev.json'),load(DATA/'queries_test.json'),
            load(DATA/'ground_truth.json'),load(REF/'article_index.json'),
            load(REF/'context_registry.json'),load(REF/'document_versions.json'),
            load(ROOT/'schemas'/'benchmark_schema.json'))

def validate_dataset(dev,test,gt,articles,chunks,docs,schema,final=False):
    issues=[]
    try: Draft202012Validator.check_schema(schema)
    except Exception as exc: return [f'JSON Schema không hợp lệ: {exc}']
    validator=lambda kind: Draft202012Validator({'$defs':schema['$defs'],'$ref':f'#/$defs/{kind}'},format_checker=FormatChecker())
    for path,rows,k in [('queries_dev.json',dev,'query'),('queries_test.json',test,'query'),('ground_truth.json',gt,'ground_truth')]:
        for n,entry in enumerate(rows):
            for e in validator(k).iter_errors(entry):
                issues.append(f'{path}[{n}]: {e.message}')
    queries=dev+test
    qids=[q.get('id') for q in queries]
    gids=[g.get('id') for g in gt]
    if not 50<=len(queries)<=300:issues.append('Benchmark phải có 50–300 câu')
    if len(dev)+len(test)==300 and len(test)!=15:
        issues.append('Bộ 300 câu phải giữ nguyên 15 câu Test')
    if len(set(qids)) != len(qids):issues.append('Trùng question ID giữa Dev và Test')
    if len(set(gids)) != len(gids):issues.append('Trùng ground-truth ID')
    if set(qids)!=set(gids):issues.append(f'Question IDs lệch ground truth; thiếu GT={sorted(set(qids)-set(gids))}, dư GT={sorted(set(gids)-set(qids))}')
    norm=lambda t:re.sub(r'[\W_]+','',str(t).casefold(),flags=re.U)
    qtexts=[norm(q.get('question','')) for q in queries]
    if len(set(qtexts))!=len(qtexts):issues.append('Có câu hỏi trùng nguyên văn hoặc dấu câu')
    # Bắt buộc kiểm tra Test freeze cho mọi lần chạy, kể cả handoff.
    # Cũng so sánh cấu trúc Test được truyền vào khi unit test cố ý biến đổi trong bộ nhớ.
    if test != load(DATA/'queries_test.json'):
        issues.append('Test set đã thay đổi so với bản nguồn đang được đóng băng')
    frozen = ROOT/'docs'/'test_questions_freeze.json'
    if not frozen.is_file():
        issues.append('Thiếu manifest đóng băng câu hỏi Test')
    else:
        expected = load(frozen)
        # Git may check out LF content as CRLF on Windows. The freeze manifest
        # hashes canonical UTF-8/LF bytes, so normalize line endings first.
        raw = (DATA/'queries_test.json').read_bytes().replace(b'\r\n', b'\n')
        digest = hashlib.sha256(raw).hexdigest()
        if (expected.get('sha256')!=digest or expected.get('test_ids')!=[q.get('id') for q in test]
                or expected.get('question_count')!=len(test)):
            issues.append('Test set đã thay đổi so với manifest khóa SHA-256')
    # Sau khi Gold Test được đóng băng, phát hiện sửa cả đáp án mà không đổi câu hỏi.
    gold_frozen=ROOT/'docs'/'test_gold_freeze.json'
    if gold_frozen.is_file():
        by_id={item.get('id'):item for item in gt}
        gold_payload={'questions':test,'test_ground_truth':[by_id.get(q.get('id')) for q in test]}
        raw=json.dumps(gold_payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        expected_gold=load(gold_frozen).get('sha256')
        if hashlib.sha256(raw).hexdigest()!=expected_gold:
            issues.append('Gold Test đã thay đổi so với manifest khóa SHA-256')
    article_index={c['article_id']:c for c in articles}
    chunk_index={c['chunk_id']:c for c in chunks}
    document_index={d['document_number']:d for d in docs}
    if len(article_index)!=len(articles):issues.append('Trùng article_id')
    if len(chunk_index)!=len(chunks):issues.append('Trùng chunk_id trong context registry')
    # Production được cấp bởi người làm Chunking; ID từ smoke không được coi là index chính thức.
    prod_file=REF/'production_chunk_index.json'
    prod_index={}
    if final or prod_file.exists():
        if not prod_file.exists():
            issues.append('Chưa nhập production_chunk_index.json từ output Chunking của nhóm')
        else:
            prod_rows=load(prod_file)
            prod_index={r['chunk_id']:r for r in prod_rows}
            if len(prod_index)!=len(prod_rows):issues.append('Production index có chunk_id trùng')
            if not prod_index:issues.append('Production index rỗng')
    if len(document_index)!=len(docs):issues.append('Trùng số hiệu văn bản trong document_versions')
    lookup={g.get('id'):g for g in gt}
    for q in queries:
        qid=q.get('id'); g=lookup.get(qid)
        if not g:continue
        docnos={c.get('document_id') for c in g.get('citations',[])}
        for c in g.get('citations',[]):
            number=c.get('document_id')
            doc=document_index.get(number)
            if doc is None:issues.append(f'{qid}: citation văn bản không tồn tại: {number}')
            else:
                # Status queries are evaluated against official metadata; provision-level queries need article evidence.
                if c.get('article')!='Trạng thái hiệu lực' and not (q.get('test_type')=='historical_law' and c.get('article')=='132' and 'hiệu lực' in q.get('question','')):
                    date=q.get('as_of_date','')
                    if doc.get('effective_date') and date<doc['effective_date']:
                        issues.append(f'{qid}: dùng quy định trước ngày có hiệu lực')
                    if doc.get('expiry_date') and date>=doc['expiry_date']:
                        issues.append(f'{qid}: dùng quy định sau khi văn bản hết hiệu lực toàn bộ')
        if q.get('test_type')=='outdated_law_trap' and not g.get('outdated_document_ids'):
            issues.append(f'{qid}: câu bẫy luật cũ thiếu outdated_document_ids')
        for old in g.get('outdated_document_ids',[]):
            if old not in document_index:issues.append(f'{qid}: thiếu metadata cho văn bản cũ {old}')
        for aid in g.get('gold_article_ids',[]):
            info=article_index.get(aid)
            if info is None:issues.append(f'{qid}: article ID không tồn tại: {aid}')
            elif info['document_number'] not in docnos:
                issues.append(f'{qid}: article {aid} không khớp nguồn citation')
        all_ids=g.get('gold_context_ids',[])+g.get('candidate_context_ids',[])
        if len(set(all_ids))!=len(all_ids):issues.append(f'{qid}: ID trùng giữa gold/candidate')
        for cid in all_ids:
            if cid in article_index:issues.append(f'{qid}: article_id không được dùng làm chunk_id: {cid}')
            if cid.startswith(('DEMO_','FAKE_','PLACEHOLDER_')):
                issues.append(f'{qid}: chunk ID giả: {cid}')
            # Production IDs are valid as unverified candidates and reviewed Gold.
            # Smoke IDs must still resolve exclusively in the smoke registry.
            is_production_gold = final and cid in g.get('gold_context_ids',[])
            info = (prod_index.get(cid) if cid in prod_index or is_production_gold
                    else chunk_index.get(cid))
            if not info:issues.append(f'{qid}: chunk ID không nằm trong registry: {cid}')
            else:
                if info['document_number'] not in docnos:issues.append(f'{qid}: chunk {cid} sai văn bản so với citation')
                if g.get('gold_article_ids') and info['article_id'] not in g['gold_article_ids']:
                    issues.append(f'{qid}: chunk {cid} không thuộc gold_article_ids')
                if not info['chunk_text'].strip():issues.append(f'{qid}: chunk {cid} rỗng')
        status=g.get('mapping_status')
        if status=='smoke_candidate' and (g.get('gold_context_ids') or not g.get('candidate_context_ids')):\
            issues.append(f'{qid}: smoke_candidate chỉ được có candidate_context_ids, không có Gold')
        if status=='partial_evidence_only' and (g.get('gold_context_ids') or not g.get('candidate_context_ids')):\
            issues.append(f'{qid}: partial_evidence_only phải có candidate, không có gold')
        if status=='not_mapped' and all_ids:
            issues.append(f'{qid}: not_mapped nhưng có context ID')
        if g.get('gold_context_ids') and not g.get('gold_context_ids_confirmed'):
            issues.append(f'{qid}: gold_context_ids chưa được xác nhận production; hãy chuyển sang candidate_context_ids')
        if g.get('gold_context_ids_confirmed') and not g.get('gold_context_ids'):
            issues.append(f'{qid}: đã xác nhận production nhưng không có gold_context_ids')
        if g.get('gold_context_ids_confirmed'):
            if status!='production_verified' or g.get('context_id_provenance')!='production_index':
                issues.append(f'{qid}: xác nhận production nhưng nhãn chưa đồng nhất')
        elif status=='production_verified':issues.append(f'{qid}: production_verified cần gold_context_ids_confirmed=true')
        if status=='production_candidate_unverified':
            if g.get('gold_context_ids') or not g.get('candidate_context_ids'):
                issues.append(f'{qid}: production candidate requires candidate IDs only, not Gold')
            if g.get('context_id_provenance')!='production_index':
                issues.append(f'{qid}: production candidate provenance must be production_index')
        if status not in ('smoke_candidate','partial_evidence_only','not_mapped','production_verified','production_candidate_unverified'):
            issues.append(f'{qid}: mapping_status không hợp lệ')
        if g.get('context_id_provenance')=='smoke_unconfirmed' and status!='smoke_candidate':
            issues.append(f'{qid}: trạng thái nguồn ID smoke chưa đồng nhất')
        if g.get('context_id_provenance')=='pending_chunking' and status=='smoke_candidate':
            issues.append(f'{qid}: pending_chunking mâu thuẫn smoke_candidate')
        # Answer quality and manual sign-off are distinct from having a PDF excerpt.
        if g.get('review_status')!='draft' and g.get('answer_kind')!='reviewed_answer':
            issues.append(f'{qid}: đã review nhưng answer_kind chưa phải reviewed_answer')
        if g.get('answer_kind')=='reviewed_answer' and g.get('review_status')=='draft':
            issues.append(f'{qid}: reviewed_answer nhưng review_status vẫn là draft')
        # Source review is an action, not something inferred from presence of a link.
        if g.get('review_status') in ('source_checked','peer_reviewed','lawyer_verified') and not g.get('verified_at'):
            issues.append(f'{qid}: đã review nhưng thiếu verified_at')
        if g.get('verified_at') and not g.get('verified_by'):
            issues.append(f'{qid}: có verified_at nhưng thiếu verified_by')
        if g.get('review_status') != 'draft' and g.get('verified_by') == 'HO_TEN_THUC_TE':
            issues.append(f"{qid}: verified_by không được để giá trị giữ chỗ 'HO_TEN_THUC_TE' khi đã qua review")
        if final:
            if g.get('answer_kind')!='reviewed_answer':
                issues.append(f'{qid}: answer chưa được biên soạn và duyệt thành câu trả lời trực tiếp')
            if g.get('review_status') not in ('source_checked','peer_reviewed','lawyer_verified') or not g.get('verified_by') or not g.get('verified_at'):
                issues.append(f'{qid}: chưa có xác minh pháp lý kèm người/ngày')
            if g.get('evidence_level') not in ('full_text_checked',):
                issues.append(f'{qid}: chứng cứ pháp lý chưa được đối chiếu toàn văn')
            for cid in g.get('gold_context_ids',[]):
                pr=prod_index.get(cid)
                if not pr:
                    issues.append(f'{qid}: gold ID không tồn tại trong production index: {cid}')
                elif g.get('gold_article_ids') and pr.get('article_id') not in g['gold_article_ids']:
                    issues.append(f'{qid}: gold ID {cid} sai Điều trong production index')
            if not g.get('gold_context_ids'):issues.append(f'{qid}: chưa có gold_context_ids')
            if not g.get('gold_context_ids_confirmed'):issues.append(f'{qid}: chưa xác nhận chunk IDs trong index')
            if status!='production_verified':issues.append(f'{qid}: chưa production_verified')
            if g.get('review_status') not in ('source_checked','peer_reviewed','lawyer_verified'):
                issues.append(f'{qid}: lời giải thích/nguồn chưa được đối chiếu')
    return issues

def check(final=False):
    args=inputs()
    problems=validate_dataset(*args,final=final)
    return problems,len(args[0]),len(args[1])

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Kiểm tra bộ benchmark')
    p.add_argument('--final',action='store_true',help='Nghiệm thu đầy đủ; chỉ PASS sau khi nạp chunks, xác minh hiệu lực/nguồn')
    p.add_argument('--show-all',action='store_true')
    a=p.parse_args()
    try: problems,dev,test=check(final=a.final)
    except Exception as e:
        print('FAIL: Không đọc được bộ benchmark:',repr(e));sys.exit(1)
    print(f'Dev={dev}; Test={test}; total={dev+test}; mode={"final" if a.final else "handoff"}; issues={len(problems)}')
    if problems:
        for issue in problems if a.show_all else problems[:12]:print(' -',issue)
        if len(problems)>12 and not a.show_all:print(f'... còn {len(problems)-12} lỗi')
        sys.exit(1)
    print('PASS. Handoff check chỉ chứng minh cấu trúc, chưa phải xác nhận gold pháp lý/production.')
