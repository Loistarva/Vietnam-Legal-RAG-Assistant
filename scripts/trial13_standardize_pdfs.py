"""Normalize actual PDF page size/scale to the testing L01 sample, losslessly.

Copies original PDFs outside the cleaner input folders; places normalized
derivatives in raw_data. Preserves original text, drawings, tables and annexes
as PDF vector content instead of rebuilding legal text from parser JSON.
"""
import hashlib
import json
from pathlib import Path
from collections import Counter
import re
import pymupdf

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/data/trial13'

def sha(data):return hashlib.sha256(data).hexdigest()
def words(pdf):
    result=[]
    for p in pdf:
        text='\n'.join(line for line in p.get_text('text',sort=True).splitlines()
            if not re.match(r'^\s*(?:Ký bởi:|Người ký:|Email:|Cơ quan:|Thời gian ký:)',line))
        result.append(Counter(ch for ch in text if not ch.isspace()))
    return result

def main():
    manifest_path=REPORT/'downloads.json'
    manifest=json.loads(manifest_path.read_text('utf8'))
    sample=ROOT/'data/raw_data/laws_and_decrees/L01.pdf'
    with pymupdf.open(sample) as doc:
        target_width,target_height=doc[0].rect.width,doc[0].rect.height
    results=[]
    for row in manifest:
        doc_id=row['document_id']
        backup=ROOT/'data/source_pdfs/trial13'/f'{doc_id}.pdf'
        source=backup if backup.exists() else ROOT/row['pdf_path']
        original_bytes=source.read_bytes()
        assert sha(original_bytes)==row['sha256'],f'Original changed: {source}'
        backup.parent.mkdir(parents=True,exist_ok=True)
        if backup.exists():assert backup.read_bytes()==original_bytes
        else:backup.write_bytes(original_bytes)
        destination=ROOT/'data/raw_data/additional_documents'/f'{doc_id}.pdf'
        with pymupdf.open(stream=original_bytes,filetype='pdf') as src:
            before=words(src)
            output=pymupdf.open()
            for index,page in enumerate(src):
                landscape=page.rect.width>page.rect.height
                width,height=(target_height,target_width) if landscape else (target_width,target_height)
                # Main text in these official source PDFs is 14 pt. Use L01's
                # 12 pt target, retaining relative sizes of headings/forms.
                scale=min(12/14,(width-48)/page.rect.width,(height-48)/page.rect.height)
                w,h=page.rect.width*scale,page.rect.height*scale
                x,y=(width-w)/2,(height-h)/2
                target=output.new_page(width=width,height=height)
                target.show_pdf_page(pymupdf.Rect(x,y,x+w,y+h),src,index,keep_proportion=True)
            output.set_metadata({'title':row['document_number'],
                'subject':'Bản chuẩn hóa phục vụ thử parser; bản gốc lưu tại data/source_pdfs/trial13',
                'creator':'trial13_standardize_pdfs.py','producer':'PyMuPDF'})
            data=output.tobytes(garbage=4,deflate=True)
            with pymupdf.open(stream=data,filetype='pdf') as checked:
                assert len(src)==len(checked)
                after=words(checked)
                if before!=after:
                    for i,(a,b) in enumerate(zip(before,after)):
                        if a!=b:print('TEXT_DIFFERENCE',doc_id,i+1,'removed',a-b,'added',b-a,flush=True)
                assert before==after,f'Text differs: {doc_id}'
                # Signature widgets/annotations are deliberately not carried to
                # the unsigned derivative. Original signatures stay in backup.
                assert all(len(a.get_images(full=True))<=len(b.get_images(full=True)) for a,b in zip(src,checked)),f'Image loss: {doc_id}'
                assert all(not p.get_text('text').count('\ufffd') for p in checked)
                page_sizes=sorted(set((round(p.rect.width,2),round(p.rect.height,2)) for p in checked))
                result={'document_id':doc_id,'source_pdf':backup.relative_to(ROOT).as_posix(),
                    'source_sha256':sha(original_bytes),'standardized_pdf':destination.relative_to(ROOT).as_posix(),
                    'standardized_sha256':sha(data),'pages':len(checked),'page_sizes_pt':page_sizes,
                    'per_page_legal_character_multisets_equal':True,'page_counts_equal':True,
                    'signature_annotations_copied':False,
                    'images_preserved':True,'vector_content_preserved':True,'main_text_target_pt':12}
            output.close()
        destination.write_bytes(data)
        row['pdf_path']=backup.relative_to(ROOT).as_posix()
        row['standardized_pdf_path']=destination.relative_to(ROOT).as_posix()
        row['standardized_sha256']=sha(data)
        row['standardization']='Letter, source 14pt scaled to 12pt; original vector content and annexes retained'
        results.append(result)
        print(doc_id,result['pages'],'pages: text/images preserved',flush=True)
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (REPORT/'standardized_pdf_check.json').write_text(json.dumps({'sample':sample.relative_to(ROOT).as_posix(),
        'method':'vector page placement, no OCR or text rewrite','documents':results},ensure_ascii=False,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
