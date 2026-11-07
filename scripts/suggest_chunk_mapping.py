"""Generate a CSV for manual review from new chunking exports. NEVER auto-label gold."""
import argparse,csv,json,re
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(path):return json.loads(Path(path).read_text(encoding='utf8'))

def extract(data):
    if isinstance(data,dict) and isinstance(data.get('chunks'),list):return data['chunks']
    if isinstance(data,list):return data
    if isinstance(data,dict) and isinstance(data.get('articles'),list):
        rows=[]
        for art in data['articles']:
            for cl in art.get('clauses',[]):rows.extend(cl.get('chunks') or [])
        return rows
    raise ValueError('Không nhận dạng được format. Cần list chunks, {chunks:[...]}, hoặc {articles:[...]}')

def get_article(c):
    if c.get('article_number') not in (None,''):
        try:return str(int(str(c['article_number']).strip()))
        except ValueError:return str(c['article_number'])
    m=re.search(r'Điều\s+(\d+)',str(c.get('article_ref','')))
    return m.group(1) if m else None

def run(src,output):
    dataset=extract(load(src))
    article_index=load(ROOT/'data'/'reference'/'article_index.json')
    articles={r['article_id']:r for r in article_index}
    lookup=defaultdict(list)
    for c in dataset:
        cid=c.get('id') or c.get('chunk_id')
        if not cid:continue
        art=get_article(c)
        doc=c.get('doc_id') or c.get('document_id')
        if doc and art:lookup[(doc,art)].append(c)
    gt=load(ROOT/'data'/'benchmark'/'ground_truth.json')
    result=[]
    for gold in gt:
        for aid in gold.get('gold_article_ids',[]):
            art=articles.get(aid)
            if not art:continue
            for c in lookup.get((art['document_id'],str(art['article_number'])),[]):
                result.append({'question_id':gold['id'],'article_id':aid,'chunk_id':c.get('id') or c.get('chunk_id'),
                               'text_preview':str(c.get('text') or c.get('chunk_text') or '')[:220],
                               'action':'REVIEW_MANUALLY__NOT_GOLD', 'production_confirmed':'NO'})
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['question_id','article_id','chunk_id','text_preview','action','production_confirmed'])
        w.writeheader();w.writerows(result)
    print(f'{len(dataset)} chunks đầu vào => {len(result)} gợi ý cần duyệt: {output}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',default='docs/new_chunk_candidates.csv');a=p.parse_args()
    run(a.input,a.output)
