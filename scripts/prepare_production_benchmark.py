#!/usr/bin/env python3
"""Production Benchmark evidence auditor and reviewed-Gold promoter.

This program never confuses automatic retrieval candidates with verified legal Gold.
Modes:
    audit: produces a complete 300-question evidence registry + audit report.
    promote: applies ONLY manually approved+signed reviews to actual ground_truth.json,
             using atomic replacement and backup; leaves unreviewed items as candidates.
    final-check: fails until *all* benchmark evidence and answers are reviewed properly.

Run from repository root, Python 3.10+; no third-party dependencies.
"""
from __future__ import annotations
import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'benchmark'
REF = ROOT / 'data' / 'reference'
REVIEW = ROOT / 'gold_evidence_review_prioritized.csv'
PLACEHOLDERS = ('tennguoikiemduyet', 'hotennguoikiemduyet', 'tennguoidakiemduyet', 'reviewer', 'yourname', 'test')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def read_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def dump_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_inputs():
    qs = read_json(DATA / 'queries_dev.json') + read_json(DATA / 'queries_test.json')
    gt = read_json(DATA / 'ground_truth.json')
    chunks = read_json(REF / 'production_chunk_index.json')
    candidates = read_csv(DATA / 'production_chunk_candidates.csv')
    vpath = DATA / 'document_version_candidates.csv'
    versions = read_csv(vpath) if vpath.exists() else []
    document_versions = read_json(REF / 'document_versions.json')
    qmap = {q['id']: q for q in qs}
    gmap = {g['id']: g for g in gt}
    cmap = {c['chunk_id']: c for c in chunks}
    issues = []
    if len(qs) != 300 or len(qmap) != 300 or len(gt) != 300 or set(gmap) != set(qmap):
        issues.append('MUST FIX: question/ground truth count or IDs not exactly 300')
    if len(chunks) != 1175 or len(cmap) != len(chunks):
        issues.append('MUST FIX: production chunk index missing chunks or duplicated IDs')
    if len(candidates) != 740:
        issues.append(f'MUST FIX: production candidates expected 740, found {len(candidates)}')
    docmap = {x['document_number']:x for x in document_versions}
    byq = collections.defaultdict(list)
    for r in candidates:
        qid, cid = r['question_id'], r['chunk_id']
        if qid not in qmap:
            issues.append(f'Unknown question {qid} in chunk candidates');continue
        chunk = cmap.get(cid)
        if not chunk:
            issues.append(f'{qid}: candidate ID not present: {cid}');continue
        if chunk['article_id'] != r['article_id'] or chunk['document_id'] != r['document_id']:
            issues.append(f'{qid}: production index vs candidates disagree for {cid}');continue
        if chunk['article_id'] not in gmap[qid].get('gold_article_ids', []):
            issues.append(f'{qid}: candidate article not in gold_article_ids: {cid}');continue
        if chunk['document_number'] not in [c['document_id'] for c in gmap[qid]['citations']]:
            issues.append(f'{qid}: candidate document not in GT citations: {cid}');continue
        byq[qid].append(cid)
    versionq = collections.defaultdict(list)
    for r in versions:
        qid,number=r.get('question_id'),r.get('document_number')
        if qid not in qmap:issues.append(f'Unknown question in document versions: {qid}');continue
        if number not in docmap:issues.append(f'{qid}: version document number not in registry: {number}');continue
        versionq[qid].append({
            'document_number': number,
            'effective_date': r.get('effective_date',''),
            'expiry_date': r.get('expiry_date',''),
            'registry_status': r.get('registry_status',''),
            'source_url': r.get('source_url',''),
            'status': 'CANDIDATE_NEEDS_LEGAL_DATE_REVIEW',
        })
    # Fall back to version-review entries, without inventing missing document numbers.
    if not versions and REVIEW.is_file():
        for r in read_csv(REVIEW):
            if r['evidence_type'] != 'DOCUMENT_VERSION':continue
            qid,number = r['question_id'],r.get('document_number','')
            if qid in qmap and number in docmap:
                d = docmap[number]
                versionq[qid].append({
                    'document_number':number,
                    'effective_date':d.get('effective_date',''),
                    'expiry_date':d.get('expiry_date',''),
                    'registry_status':d.get('source_status') or d.get('status',''),
                    'source_url':r.get('source_url') or d.get('source_url',''),
                    'status':'CANDIDATE_NEEDS_LEGAL_DATE_REVIEW',
                })
    coverage = {qid for qid in qmap if byq[qid] or versionq[qid]}
    if len(coverage) != 300:
        issues.append(f'MUST FIX: only {len(coverage)}/300 questions have evidence candidate; missing {sorted(set(qmap)-coverage)}')
    not_found = sorted({cid for g in gt for cid in g.get('candidate_context_ids', []) if cid not in cmap})
    if not_found: issues.append(f'MUST FIX: {len(not_found)} candidate_context_ids absent from production index')
    return qs,gt,cmap,byq,versionq,issues


def build_audit():
    qs, gt, cmap, byq, versionq, errors = validate_inputs()
    byid = {g['id']:g for g in gt}
    registry = []
    for q in qs:
        qid = q['id']; g=byid[qid]
        # Use source CSV as the canonical candidate list, not potentially stale smoke IDs.
        candidates = list(dict.fromkeys(byq[qid]))
        article_ids = set(g.get('gold_article_ids', []))
        evidenced_articles = {cmap[cid]['article_id'] for cid in candidates}
        missing_articles = sorted(article_ids - evidenced_articles) if candidates else []
        flags=[]
        if not candidates:flags.append('NO_CHILD_CHUNK_CANDIDATE')
        if versionq[qid]:flags.append('NEEDS_DOCUMENT_VERSION_REVIEW')
        if missing_articles:flags.append('MISSING_ARTICLE:'+','.join(missing_articles))
        if g.get('answer_kind') != 'reviewed_answer':flags.append('ANSWER_NOT_REVIEWED')
        if g.get('gold_context_ids') and not g.get('gold_context_ids_confirmed'):
            flags.append('UNCONFIRMED_GOLD_ID')
        registry.append({
            'question_id':qid, 'question':q['question'],
            'as_of_date':q.get('as_of_date',''),
            'candidate_chunk_ids':candidates,
            'document_version_candidates':versionq[qid],
            'expected_article_ids':sorted(article_ids),
            'missing_article_ids':missing_articles,
            'confirmed_gold_chunk_ids':g.get('gold_context_ids', []) if g.get('gold_context_ids_confirmed') else [],
            'answer_status':g.get('answer_kind', 'unreviewed'),
            'flags':flags,
            'evidence_status':'GOLD_VERIFIED' if g.get('gold_context_ids_confirmed') and g.get('review_status') != 'draft' else 'CANDIDATE_NOT_GOLD'
        })
    out = DATA / 'production_evidence_registry.json'
    dump_json(out,registry)
    flags=collections.Counter(f for x in registry for f in x['flags'])
    report={
        'question_count':len(qs),'production_chunk_count':len(cmap),
        'chunk_candidate_rows':sum(len(v) for v in byq.values()),
        'questions_with_chunk_candidates':sum(bool(v) for v in byq.values()),
        'version_candidate_rows':sum(len(v) for v in versionq.values()),
        'questions_with_version_candidates':sum(bool(v) for v in versionq.values()),
        'questions_with_any_candidate':sum(bool(x['candidate_chunk_ids'] or x['document_version_candidates']) for x in registry),
        'confirmed_gold_questions':sum(x['evidence_status']=='GOLD_VERIFIED' for x in registry),
        'review_flags':dict(sorted(flags.items())),
        'errors':errors,
        'can_claim_final_gold_pass':not errors and all(x['evidence_status']=='GOLD_VERIFIED' and not x['flags'] for x in registry),
        'notes':[
            'Candidate IDs are real production chunk IDs, NOT legally approved Gold IDs.',
            'Version evidence is NOT a Child Chunk and cannot be inserted as fake chunk IDs.',
            'Luật 52/2014/QH13 source PDF in prior audit stops at Điều 131; Điều 132–133 must be supplied from complete authoritative source.',
            'Use parser on PDF independently; parser does NOT need gold_context_ids to produce JSON.',
        ],
    }
    dump_json(DATA/'production_evidence_audit.json',report)
    print('=== PRODUCTION EVIDENCE AUDIT ===')
    for k in ('question_count','production_chunk_count','chunk_candidate_rows','questions_with_chunk_candidates','version_candidate_rows','questions_with_version_candidates','questions_with_any_candidate','confirmed_gold_questions','can_claim_final_gold_pass'):
        print(k,':',report[k])
    print('Review flags:',report['review_flags'])
    if errors: print('ERRORS:\n'+'\n'.join(errors[:15]))
    print('Output:',out)
    return report


def validate_reviewer(name,date):
    normalized=re.sub('[^a-z]','',name.lower())
    if len(normalized)<5 or any(x in normalized for x in PLACEHOLDERS):
        raise ValueError('Use the actual full name of the human reviewer; no placeholders')
    try:d=dt.date.fromisoformat(date)
    except ValueError:raise ValueError('review date format YYYY-MM-DD')
    if d>dt.date.today(): raise ValueError('Review date cannot be in the future')


def promote(name,date,yes_to_backup=False):
    validate_reviewer(name,date)
    if not REVIEW.is_file(): raise FileNotFoundError('Missing '+str(REVIEW))
    qs,gt,cmap,byq,versionq,errors=validate_inputs()
    if errors:raise ValueError('Input failed checks; promotion stopped: '+' | '.join(errors[:8]))
    review=read_csv(REVIEW)
    allowed={'APPROVE','REJECT',''}
    decisions=collections.defaultdict(list)
    for r in review:
        dec=r.get('review_decision','').strip().upper()
        if dec not in allowed:
            raise ValueError('Invalid review_decision '+repr(dec))
        if dec=='APPROVE':
            if r.get('evidence_type')!='CHILD_CHUNK':
                raise ValueError('Version-only approval requires separate legal/temporal gold support, not chunk ID')
            if r.get('source_verified','').strip().upper()!='YES' or r.get('answer_verified','').strip().upper()!='YES':
                raise ValueError(r['question_id']+': must verify both source and answer')
            if not r.get('reviewed_answer','').strip() or not r.get('reviewed_explanation','').strip() or not r.get('review_notes','').strip():
                raise ValueError(r['question_id']+': missing reviewed answer/explanation/notes')
            qid,cid=r['question_id'],r['chunk_id']
            if cid not in byq.get(qid,[]): raise ValueError(qid+': approval chunk ID is not a valid candidate')
            if r['article_id']!=cmap[cid]['article_id']:
                raise ValueError(qid+': reviewed article disagrees with production index')
            decisions[qid].append(r)
    if not decisions:raise ValueError('No approved candidates; nothing changed')
    # Don't violate a frozen Gold Test set.
    testids={q['id'] for q in read_json(DATA/'queries_test.json')}
    if (ROOT/'docs'/'test_gold_freeze.json').exists() and testids.intersection(decisions):
        raise ValueError('Frozen test gold would change; refusing to promote')
    bygt={g['id']:g for g in gt}
    for qid,rs in decisions.items():
        g=bygt[qid]
        if g.get('gold_context_ids_confirmed'):
            raise ValueError(qid+': already confirmed; refusing overwrite')
        # Multi-hop citations require reviewers to sign off every declared gold article.
        expected=set(g.get('gold_article_ids', []))
        approved_articles={cmap[r['chunk_id']]['article_id'] for r in rs}
        if expected and not expected.issubset(approved_articles):
            raise ValueError(qid+': missing approved evidence for articles '+','.join(sorted(expected-approved_articles)))
        answers={r['reviewed_answer'].strip() for r in rs}
        explanations={r['reviewed_explanation'].strip() for r in rs}
        if len(answers)!=1 or len(explanations)!=1:raise ValueError(qid+': inconsistent reviews')
        approved_ids=list(dict.fromkeys(r['chunk_id'] for r in rs))
        g['answer']=answers.pop();g['explanation']=explanations.pop()
        g['gold_context_ids']=approved_ids
        g['candidate_context_ids']=[cid for cid in byq[qid] if cid not in approved_ids]
        g['mapping_status']='production_verified'
        g['gold_context_ids_confirmed']=True
        g['context_id_provenance']='production_index'
        g['answer_kind']='reviewed_answer'
        g['review_status']='source_checked'
        g['verified_by']=name;g['verified_at']=date
        # Do not claim full-text checked without full-text verification proof.
        g['evidence_level']='chunk_text_matched_unverified'
    original=DATA/'ground_truth.json'
    backup_dir=Path(tempfile.mkdtemp(prefix='benchmark_gold_backup_'))
    shutil.copy2(original,backup_dir/'ground_truth.json')
    staged=DATA/'.ground_truth.atomic.tmp'
    staged.write_text(json.dumps(gt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        staged.replace(original)
    except Exception:
        if staged.exists():staged.unlink()
        raise
    print('PROMOTED reviewed Gold questions:',len(decisions))
    print('Original backed up:',backup_dir/'ground_truth.json')
    print('Gold still needing review:',300-sum(bool(g.get('gold_context_ids_confirmed')) for g in gt))
    print('Note: promotion reflects reviewer-signoff in CSV, NOT independent legal verification by this script.')
    print('Note: evidence_level is not full_text_checked; --final remains blocked until full legal review.')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('mode',choices=['audit','promote-reviewed','final-check'])
    ap.add_argument('--reviewer')
    ap.add_argument('--review-date')
    args=ap.parse_args()
    if args.mode=='audit':
        report=build_audit()
        sys.exit(1 if report['errors'] else 0)
    if args.mode=='promote-reviewed':
        if not args.reviewer or not args.review_date:
            ap.error('--reviewer and --review-date are required for promote-reviewed')
        promote(args.reviewer,args.review_date)
        report=build_audit()
        sys.exit(1 if report['errors'] else 0)
    if args.mode=='final-check':
        report=build_audit()
        if not report['can_claim_final_gold_pass']:
            print('BLOCKED: Cannot claim official 300/300 Gold PASS while review/source gaps remain.')
            sys.exit(2)
        print('Ready for external repo final validation (still run scripts/validate_benchmark.py --final).')

if __name__=='__main__':
    main()
