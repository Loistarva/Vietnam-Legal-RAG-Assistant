"""Read-only PDF format/native extraction comparison; never rewrites a PDF."""
import contextlib
import io
import json
from collections import Counter
from pathlib import Path
import sys
import pymupdf
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'parser'))
import cleaner
import parser as legal_parser
from test_parser import check_doc_structure

def pdf_info(path):
    with pymupdf.open(path) as pdf:
        texts=[page.get_text('text',sort=True) for page in pdf]
        fonts=Counter()
        for page in pdf:
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    for span in line.get('spans',[]):
                        fonts[(span['font'],round(span['size'],1))]+=len(span['text'])
        return {'pages':len(pdf),'page_sizes_pt':sorted(set((round(p.rect.width,1),round(p.rect.height,1)) for p in pdf)),
                'top_fonts':[{'font':f,'size_pt':s,'characters':n} for (f,s),n in fonts.most_common(5)],
                'sparse_pages':[i+1 for i,t in enumerate(texts) if len(t.strip())<80],
                'replacement_characters':sum(t.count('\ufffd') for t in texts),
                'nul_characters':sum(t.count('\x00') for t in texts)},texts

def main():
    manifest=json.loads((ROOT/'reports/data/trial13/downloads.json').read_text('utf8'))
    sample=ROOT/'data/raw_data/laws_and_decrees/L01.pdf'
    sample_info,_=pdf_info(sample)
    results=[]
    for row in manifest:
        path=ROOT/row['pdf_path']
        info,pages=pdf_info(path)
        raw=cleaner.normalize_extracted_text('\n\n'.join(cleaner.normalize_extracted_text(t) for t in pages))
        clean,_=cleaner.clean_extracted_text(raw)
        existing=json.loads((ROOT/'parser/parsed_jsons'/f"{row['document_id']}.json").read_text('utf8'))
        with contextlib.redirect_stdout(io.StringIO()):
            meta=legal_parser.extract_metadata(clean,str(path))
            direct=legal_parser.parse_raw_text_to_legal_doc(clean,row['document_id'],meta)
        errors,notes=check_doc_structure(direct)
        different=[a['article_number'] for a,b in zip(direct['articles'],existing['articles']) if a!=b]
        results.append({'document_id':row['document_id'],'pdf_path':row['pdf_path'],**info,
                        'native_pipeline_articles':len(direct['articles']),
                        'prepared_pipeline_articles':len(existing['articles']),
                        'structure_errors':errors,'different_articles_before_preparation':different,
                        'same_article_count':len(direct['articles'])==len(existing['articles'])})
    out={'sample_pdf':sample.relative_to(ROOT).as_posix(),'sample':sample_info,
         'pdfs_reformatted':False,'documents':results,
         'all_native_article_counts_match':all(x['same_article_count'] for x in results),
         'all_native_structures_valid':all(not x['structure_errors'] for x in results)}
    (ROOT/'reports/data/trial13/pdf_check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    paths=[sample]+[ROOT/x['pdf_path'] for x in manifest]
    sheet=Image.new('RGB',(2000,2130),'#ddd')
    draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(paths):
        with pymupdf.open(path) as pdf:
            pix=pdf[0].get_pixmap(matrix=pymupdf.Matrix(.65,.65),alpha=False)
        im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        im.thumbnail((490,670))
        x=(i%4)*500;y=(i//4)*532
        im.thumbnail((490,500))
        sheet.paste(im,(x,y+25))
        draw.text((x+5,y+5),('SAMPLE: ' if i==0 else '')+path.stem,fill='black')
    dest=ROOT/'tmp/trial13/pdf_contact_sheet.png'
    dest.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(dest)
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
