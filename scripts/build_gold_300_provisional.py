#!/usr/bin/env python3
"""Create provisional 300/300 evidence ID mappings, never reviewer approvals.
Usage: python build_gold_300_provisional.py --root <benchmark_repo> --output <output_dir>
This intentionally does NOT overwrite production ground_truth.json or validators.
"""
from __future__ import annotations
import argparse, csv, datetime, hashlib, json, re, sys
from collections import defaultdict, Counter
from pathlib import Path

def read_json(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def load_candidates(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def build(root, out):
    data=root/'data'/'benchmark'
    ref=root/'data'/'reference'
    gt=read_json(data/'ground_truth.json')
    chunks=read_json(ref/'production_chunk_index.json')
    versions=read_json(ref/'document_versions.json')
    suggestion_rows=load_candidates(data/'production_chunk_candidates.csv')
    idx={x['chunk_id']:x for x in chunks}
    if len(idx)!=len(chunks): raise ValueError('Duplicate production chunk IDs')
    docs={x['document_number'].casefold():x for x in versions}
    ranked=defaultdict(list)
    for r in suggestion_rows:
        ranked[r['question_id']].append(r)
    for items in ranked.values():
        items.sort(key=lambda x:(int(x.get('candidate_rank') or 999),-float(x.get('lexical_overlap') or 0)))
    full=[]
    report=[]
    version_chunks={}
    no_support=[]
    for g in gt:
        qid=g['id']
        evidence=[]; evidence_tier=[]; alerts=[]
        cited_docs={x['document_id'] for x in g.get('citations',[])}
        gold_articles=g.get('gold_article_ids') or []
        if g.get('gold_context_ids'):
            for cid in g['gold_context_ids']:
                if cid not in idx: raise ValueError(f'Existing gold {cid} missing from index: {qid}')
                if idx[cid]['document_number'] not in cited_docs: raise ValueError(f'Existing gold wrong document: {qid}')
                evidence.append(cid); evidence_tier.append('EXISTING_REVIEWED_ID')
        # One candidate for each referenced article, subject to independent legal review.
        for aid in gold_articles:
            viable=[]
            for r in ranked[qid]:
                cid=r['chunk_id']
                if cid in idx and idx[cid]['article_id']==aid and idx[cid]['document_number'] in cited_docs:
                    viable.append(r)
            if viable:
                cid=viable[0]['chunk_id']
                if cid not in evidence:
                    evidence.append(cid); evidence_tier.append('UNREVIEWED_CHUNK_PROPOSAL')
            else:
                alerts.append('MISSING_ARTICLE_CANDIDATE:'+aid)
        # One original legal-text case was previously excluded from candidate matching:
        # HN_051 is a provision question, so use the actual Law 2000 Article 10(5) chunk.
        if qid=='HN_051':
            cid='l02_art_10_chunk_5'
            if cid in idx and idx[cid]['article_id']=='L02_D10' and cid not in evidence:
                evidence.append(cid);evidence_tier.append('UNREVIEWED_CHUNK_PROPOSAL')
            else:
                alerts.append('MISSING_L02_ARTICLE_10_5_CHUNK')
        # Questions with no cited articles (document validity, temporal law): add source-backed version contexts.
        needs_version=(qid in {f'HN_{n:03}' for n in range(37,61)}) or bool(alerts)
        if needs_version:
            # Comparison questions explicitly mention a second legal instrument.
            # Add its status evidence rather than silently treating one source as sufficient.
            compared_docs=set(cited_docs)
            if qid=='HN_043': compared_docs.add('10/2015/NĐ-CP')
            if qid=='HN_044': compared_docs.add('207/2025/NĐ-CP')
            for number in sorted(compared_docs):
                doc=docs.get(number.casefold())
                if not doc:
                    alerts.append('MISSING_VERSION_METADATA:'+number)
                    continue
                stable='version_'+hashlib.sha256(number.casefold().encode()).hexdigest()[:16]
                if stable not in version_chunks:
                    effective=doc.get('effective_date','')
                    expiry=doc.get('expiry_date','')
                    status=doc.get('source_status') or doc.get('status','')
                    version_chunks[stable]={
                        'chunk_id':stable,
                        'evidence_type':'DOCUMENT_VERSION_METADATA',
                        'document_number':number,
                        'title':doc.get('title') or number,
                        'effective_date':effective,
                        'expiry_date':expiry,
                        'status':status,
                        'source_url':doc.get('source_url',''),
                        'verification_scope':doc.get('verification_scope','document_level_only'),
                        'chunk_text':f'Văn bản: {number}; Có hiệu lực từ: {effective}; Hết hiệu lực từ: {expiry or "chưa ghi nhận"}; Trạng thái: {status}.',
                        'review_required':True,
                        'source':'data/reference/document_versions.json',
                    }
                if stable not in evidence:
                    evidence.append(stable);evidence_tier.append('UNREVIEWED_VERSION_METADATA')
        if not evidence:
            alerts.append('NO_EVIDENCE_ID')
            no_support.append(qid)
        # JSON specifically requested: 300 populated gold_context_ids, but PROVISIONAL only.
        x=dict(g)
        x['gold_context_ids']=evidence
        x['gold_id_assignment_status']='PROVISIONAL_NOT_LEGALLY_VERIFIED'
        x['provisional_evidence_types']=evidence_tier
        x['provisional_review_alerts']=alerts
        # Avoid claiming new reviewers. For existing reviewed records, preserve flags,
        # but if we appended unreviewed sources the entire record is not fully confirmed.
        if any(t!='EXISTING_REVIEWED_ID' for t in evidence_tier):
            x['gold_context_ids_confirmed']=False
            x['review_status']='draft'
            x['verified_by']=None
            x['verified_at']=None
            x['answer_kind']='draft_answer_unreviewed'
            x['mapping_status']='production_candidate_unverified'
        # This file is intentionally not validator-compliant: provisional IDs in Gold are
        # forbidden by the project's honest production validator.
        full.append(x)
        report.append({
            'question_id':qid, 'context_ids':';'.join(evidence),
            'context_count':len(evidence), 'evidence_types':';'.join(evidence_tier),
            'review_required':'YES' if x['gold_id_assignment_status'].startswith('PROVISIONAL') else 'NO',
            'issues':';'.join(alerts), 'verified_gold':'YES' if g.get('gold_context_ids_confirmed') else 'NO',
        })
    if len(gt)!=300 or len(full)!=300: raise ValueError(f'expected 300 questions, found {len(gt)}')
    all_ids=set(idx)|set(version_chunks)
    unknown=sorted({cid for g in full for cid in g['gold_context_ids'] if cid not in all_ids})
    if unknown or no_support: raise ValueError(f'unresolved IDs={unknown}; empty={no_support}')
    if len(all_ids)!=len(idx)+len(version_chunks): raise ValueError('Duplicate version ID overlaps production index')
    if {g['id'] for g in full}!={g['id'] for g in gt}: raise ValueError('ID set changed')
    if any(not g['gold_context_ids'] for g in full): raise ValueError('empty context ids')
    # Never overwrite, even in an output directory.
    outputs={
        'ground_truth.full_gold_ids_PROVISIONAL.json':full,
        'data/reference/document_version_evidence_index.json':list(version_chunks.values()),
        'data/reference/all_evidence_index_PROVISIONAL.json':chunks+list(version_chunks.values()),
        'full_gold_ids_audit.json':{
            'question_count':len(full), 'nonempty_gold_context_ids':sum(bool(g['gold_context_ids']) for g in full),
            'source_child_chunk_count':len(chunks),'version_evidence_count':len(version_chunks),
            'indexed_evidence_count':len(all_ids),
            'unresolved_id_count':len(unknown),
            'questions_with_source_gap':[
                r['question_id'] for r in report if r['issues']
            ],
            'unreviewed_question_count':sum(g['review_status']=='draft' for g in full),
            'warning': 'PROVISIONAL only. These 300 IDs have NOT been fully verified against official law, and are NOT production Gold. Do not replace ground_truth.json. --final is expected to remain blocked.'
        }
    }
    if out.exists() and any(out.iterdir()): raise FileExistsError(f'Output is not empty: {out}')
    out.mkdir(parents=True,exist_ok=True)
    for name,obj in outputs.items(): write_json(out/name,obj)
    with (out/'full_gold_ids_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(report[0].keys()));wr.writeheader();wr.writerows(report)
    print('PROVISIONAL_MAPPING_OK')
    print('Questions:',len(full))
    print('Nonempty gold_context_ids:',sum(bool(g['gold_context_ids']) for g in full))
    print('Version metadata evidence contexts:',len(version_chunks))
    print('No orphan context IDs:',len(unknown)==0)
    print('Flagged for missing source:',[(r['question_id'],r['issues']) for r in report if r['issues']])
    print('Production GOLD certified: NO')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--output',type=Path,default=Path('full_gold_proposals'))
    a=p.parse_args(); build(a.root.resolve(),a.output.resolve())
if __name__=='__main__':main()
