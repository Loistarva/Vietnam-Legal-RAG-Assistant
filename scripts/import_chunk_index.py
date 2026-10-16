"""Import JSONL chunk output from chunking teammate and create article-aligned suggestions.

Does NOT alter ground_truth, smoke registry, or review_status. Does NOT claim production was verified.
Run from repo root:
  python scripts/import_chunk_index.py --input path/to/chunks.jsonl
"""
import argparse, csv, hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def compact(s):return ' '.join(str(s or '').split())
def tokens(s):return set(re.findall(r'\w+',compact(s).casefold(),re.UNICODE))
def ingest(file,out,report,limit=5):
    if not file.exists():raise FileNotFoundError(file)
    rows=[]
    if file.suffix.lower()=='.jsonl':
        for n,line in enumerate(file.read_text(encoding='utf-8-sig').splitlines(),1):
            if line.strip():
                try:rows.append(json.loads(line))
                except Exception as exc: raise ValueError(f'JSONL line {n}: {exc}')
    else:
        data=load(file)
        if isinstance(data,dict) and 'chunks' in data: data=data['chunks']
        if not isinstance(data,list):raise ValueError('JSON must be a list of chunks')
        rows=data
    articles=load(ROOT/'data/reference/article_index.json')
    article_idx={(a['document_id'],str(a['article_number'])):a for a in articles}
    source_sha=hashlib.sha256(file.read_bytes()).hexdigest()
    raw_ids=[];normalized=[];unmatched=[];number_conflicts=[]
    for row in rows:
        cid=str(row.get('chunk_id') or '').strip()
        code=str(row.get('document_id') or '').strip()
        number=str(row.get('article_number') or '').strip()
        txt=str(row.get('chunk_text') or '').strip()
        raw_ids.append(cid)
        if not cid or not code or not number or not txt:raise ValueError(f'Chunk missing id/doc/article/text: {row}')
        article=article_idx.get((code,number))
        if not article:
            unmatched.append((cid,code,number))
        docno=str(row.get('document_number') or '').strip()
        if article and docno and docno!=article['document_number']:
            number_conflicts.append((cid,docno,article['document_number']))
        normalized.append({'chunk_id':cid,'document_id':code,'document_number':article['document_number'] if article else docno,
                           'article_id':article['article_id'] if article else '', 'article_number':number,
                           'clause_id':str(row.get('clause_id') or ''),'chunk_text':txt,'source_chunk_file':str(file.name),
                           'source_chunk_sha256':source_sha})
    if len(raw_ids)!=len(set(raw_ids)):raise ValueError('Duplicate chunk_id in imported chunks')
    if number_conflicts:
        print(f'WARNING: {len(number_conflicts)} chunk metadata document number conflicts: {number_conflicts[:4]}')
    q=load(ROOT/'data/benchmark/queries_dev.json')+load(ROOT/'data/benchmark/queries_test.json')
    g={x['id']:x for x in load(ROOT/'data/benchmark/ground_truth.json')}
    by_article=defaultdict(list)
    for row in normalized:by_article[row['article_id']].append(row)
    proposals=[]
    for query in q:
        gt=g[query['id']]; ts=tokens(query['question'])
        candidates=[]
        for aid in gt['gold_article_ids']:
            for row in by_article[aid]:
                overlap=len(ts&tokens(row['chunk_text']))
                score=round(overlap / max(1,len(ts)),4)
                candidates.append((score,row))
        candidates.sort(key=lambda v:(-v[0],v[1]['chunk_id']))
        for i,(score,row) in enumerate(candidates[:limit],1):
            proposals.append({'question_id':query['id'],'candidate_rank':i,'chunk_id':row['chunk_id'],
                'article_id':row['article_id'],'document_id':row['document_id'],'lexical_overlap':score,
                'review_required':'YES','status':'SUGGESTION_NOT_GOLD','text_preview':compact(row['chunk_text'])[:420]})
    if out.exists() or report.exists():raise FileExistsError('Output already exists: move previous files aside before importing new index')
    out.parent.mkdir(parents=True,exist_ok=True);report.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(normalized,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with report.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['question_id','candidate_rank','chunk_id','article_id','document_id','lexical_overlap','review_required','status','text_preview']);writer.writeheader();writer.writerows(proposals)
    summary={'input_chunks':len(normalized),'matched_articles':len(set(r['article_id'] for r in normalized if r['article_id'])),'unmatched':len(unmatched),
             'metadata_number_conflicts':len(number_conflicts),'candidate_rows':len(proposals),
             'questions_with_candidates':len(set(x['question_id'] for x in proposals)),
             'input_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
             'warning':'Only article match and keyword overlap; production verification requires index/reviewer approval.'}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'data/reference/production_chunk_index.json');p.add_argument('--candidates',type=Path,default=ROOT/'docs/production_chunk_candidates.csv');p.add_argument('--top-k',type=int,default=5)
    a=p.parse_args();ingest(a.input,a.output,a.candidates,a.top_k)
