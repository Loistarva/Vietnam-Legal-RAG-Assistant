"""Non-blocking, deterministic review-priority audit of DRAFT benchmark items.

Does not infer legal correctness from citations, excerpts or automatically extracted PDFs.
Outputs human review queue; nothing is promoted to verified Gold.
"""
from __future__ import annotations
import argparse,csv,json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def audit(private_dir: Path|None=None):
    dev=load(ROOT/'data/benchmark/queries_dev.json')
    test=load(ROOT/'data/benchmark/queries_test.json')
    truth={g['id']:g for g in load(ROOT/'data/benchmark/ground_truth.json')}
    article={a['article_id']:a for a in load(ROOT/'data/reference/article_index.json')}
    docs={d['document_number']:d for d in load(ROOT/'data/reference/document_versions.json')}
    rows=[]
    risk_counts=Counter()
    for split,items in [('Dev',dev),('Test',test)]:
        for q in items:
            g=truth[q['id']];risks=[];a=g['answer'];text=q['question']
            if g['answer_kind']=='extracted_article_text_unreviewed':
                risks.append('PDF_EXCERPT_NOT_DIRECT_ANSWER')
            if g['answer_kind']=='draft_answer_unreviewed':
                risks.append('DRAFT_ANSWER_NOT_LEGAL_REVIEWED')
            if g['review_status']=='draft':
                risks.append('MISSING_LEGAL_REVIEW')
            if g['mapping_status']=='smoke_candidate':
                risks.append('SMOKE_IDS_NOT_PRODUCTION')
            elif g['mapping_status']=='partial_evidence_only':
                risks.append('PARTIAL_CONTEXT_EVIDENCE')
            elif g['mapping_status']=='not_mapped':
                risks.append('NO_CHUNK_ID')
            if g['gold_article_ids'] and any(article.get(aid,{}).get('verification_status')!='verified' for aid in g['gold_article_ids']):
                risks.append('ARTICLE_REFERENCE_NOT_HUMAN_VERIFIED')
            if q['test_type'] in ('partially_expired','outdated_law_trap','historical_law'):
                risks.append('TEMPORAL_LAW_STATUS_NEEDS_REVIEW')
            if any(docs.get(c['document_id'],{}).get('provision_status')=='document_level_only' for c in g['citations']):
                risks.append('DOCUMENT_STATUS_ONLY')
            if len(a)>800:risks.append('VERY_LONG_DRAFT_ANSWER')
            if re.search(r'\b(KẾT HÔN|LY HÔN|QUAN HỆ GIỮA VỢ VÀ CHỒNG|CẤP DƯỠNG)\s*$',a):
                risks.append('POSSIBLE_PDF_CHAPTER_HEADING_LEAK')
            if any(k in text.casefold() for k in ['trường hợp liên quan đến','những nội dung pháp lý cụ thể nào','được giải quyết theo căn cứ nào','cần đáp ứng những yêu cầu cụ thể nào']):
                risks.append('QUESTION_MAY_BE_TOO_GENERIC')
            if q['question_type']=='multi_hop' and len(g['gold_article_ids'])<2:
                risks.append('MULTIHOP_MISSING_ARTICLE_REFERENCE')
            for r in risks:risk_counts[r]+=1
            rows.append({'question_id':q['id'],'split':split,'question_type':q['question_type'],
                         'test_type':q['test_type'],'answer_kind':g['answer_kind'],
                         'mapping_status':g['mapping_status'],'risk_count':len(risks),
                         'review_flags':'|'.join(risks),'question':q['question'],
                         'gold_article_ids':'|'.join(g['gold_article_ids']),
                         'review_status':g['review_status']})
    rows.sort(key=lambda row: (row['split']=='Test',-int(row['risk_count']),row['question_id']))
    report={'total_questions':len(rows),'dev':len(dev),'test':len(test),
            'all_ground_truth_still_draft':all(g['review_status']=='draft' for g in truth.values()),
            'confirmed_gold_context_ids':sum(len(g['gold_context_ids']) for g in truth.values()),
            'smoke_candidates_relocated_to_candidate_context_ids':sum(g['mapping_status']=='smoke_candidate' and bool(g['candidate_context_ids']) for g in truth.values()),
            'extracted_pdf_draft_answers':sum(g['answer_kind']=='extracted_article_text_unreviewed' for g in truth.values()),
            'review_flags':dict(sorted(risk_counts.items())),
            'note':'Cảnh báo để người kiểm duyệt ưu tiên, không phải kết luận pháp luật đúng/sai hoặc thống kê gold verified.'}
    docs_path=ROOT/'docs';docs_path.mkdir(exist_ok=True)
    (docs_path/'quality_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (docs_path/'quality_review_priorities_dev.csv').open('w',encoding='utf-8-sig',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(r for r in rows if r['split']=='Dev')
    if private_dir is not None:
        private_dir.mkdir(parents=True,exist_ok=True)
        with (private_dir/'quality_review_priorities_test_RESTRICTED.csv').open('w',encoding='utf-8-sig',newline='') as fp:
            writer=csv.DictWriter(fp,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(r for r in rows if r['split']=='Test')
    return report
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--private-dir',type=Path,default=None,help='Nơi lưu review Test được phân quyền; mặc định KHÔNG tạo bảng Test trong repo.')
    args=ap.parse_args()
    print(json.dumps(audit(private_dir=args.private_dir),ensure_ascii=False,indent=2))
