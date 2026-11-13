"""Download original official PDFs for the isolated 13-document parser trial."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import concurrent.futures
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/data/trial13'
CANDIDATES = [
    ('l_60_2014_qh13', '60/2014/QH13', 178129, 'https://congbao.chinhphu.vn/van-ban/luat-so-60-2014-qh13-5264.htm'),
    ('l_52_2010_qh12', '52/2010/QH12', 96052, 'https://congbao.chinhphu.vn/van-ban/luat-so-52-2010-qh12-2961/1192.htm'),
    ('l_13_2022_qh15', '13/2022/QH15', 207711, None),
    ('tt_10_2020_tt_btp', '10/2020/TT-BTP', None, 'https://congbao.chinhphu.vn/van-ban/thong-tu-so-10-2020-tt-btp-33164.htm'),
    ('nd_06_2011_nd_cp', '06/2011/NĐ-CP', None, 'https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-06-2011-nd-cp-729/3966.htm'),
    ('l_35_2013_qh13', '35/2013/QH13', 169373, 'https://congbao.chinhphu.vn/van-ban/luat-so-35-2013-qh13-6398/3284.htm'),
    ('nd_28_2012_nd_cp', '28/2012/NĐ-CP', None, 'https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-28-2012-nd-cp-117.htm'),
    ('l_51_2010_qh12', '51/2010/QH12', 96045, 'https://congbao.chinhphu.vn/van-ban/luat-so-51-2010-qh12-3086.htm'),
    ('nd_19_2011_nd_cp', '19/2011/NĐ-CP', 99538, 'https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-19-2011-nd-cp-4925.htm'),
    ('nd_56_2017_nd_cp', '56/2017/NĐ-CP', 189758, 'https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-56-2017-nd-cp-23704.htm'),
    ('nd_76_2023_nd_cp', '76/2023/NĐ-CP', 208906, 'https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-76-2023-nd-cp-40354/46907.htm'),
    ('nd_114_2016_nd_cp', '114/2016/NĐ-CP', 185624, 'https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-114-2016-nd-cp-20467/14937.htm'),
    ('nd_15_2014_nd_cp', '15/2014/NĐ-CP', 172588, 'https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-15-2014-nd-cp-6628/3438.htm'),
]

def get(url):
    r = requests.get(url, timeout=50)
    r.raise_for_status()
    return r

def one(candidate):
    doc_id, number, official_id, alternate = candidate
    cache_path = REPORT/'downloads.json'
    if cache_path.exists():
        for cached in json.loads(cache_path.read_text(encoding='utf-8')):
            if cached['document_id'] == doc_id and cached.get('download_status') == 'downloaded':
                path = ROOT / cached['pdf_path']
                if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == cached['sha256']:
                    return cached
    page_url = f'https://vanban.chinhphu.vn/?pageid=27160&docid={official_id}' if official_id else alternate
    report = {'document_id': doc_id, 'document_number': number, 'source_url': page_url}
    try:
        page = get(page_url)
        soup = BeautifulSoup(page.content, 'html.parser')
        fields = {}
        for tr in soup.select('tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) == 2:
                label, value = [c.get_text(' ', strip=True) for c in cells]
                if label in ['Số ký hiệu', 'Ngày ban hành', 'Ngày có hiệu lực', 'Loại văn bản', 'Cơ quan ban hành', 'Trích yếu']:
                    fields[label] = value
        report['official_fields'] = fields
        if not official_id:
            text = soup.get_text(' ', strip=True)
            dates = re.search(r'Ban hành:\s*(\d{2}/\d{2}/\d{4})\s*-\s*Hiệu lực:\s*(\d{2}/\d{2}/\d{4})', text)
            if dates:
                fields.update({'Ngày ban hành':dates[1].replace('/','-'), 'Ngày có hiệu lực':dates[2].replace('/','-')})
            is_tt = doc_id.startswith('tt_')
            fields.update({'Số ký hiệu':number,'Loại văn bản':'Thông tư' if is_tt else 'Nghị định','Cơ quan ban hành':'Bộ Tư pháp' if is_tt else 'Chính phủ','Trích yếu':soup.select_one('h1').get_text(' ',strip=True)})
        REPORT.mkdir(parents=True, exist_ok=True)
        (REPORT / f'{doc_id}.source.html').write_bytes(page.content)
        urls = [urljoin(page_url, a['href']) for a in soup.select('a.view-file[href]') if '.pdf' in a['href'].lower()]
        if alternate:
            if '.pdf' in alternate or 'format=pdf' in alternate:
                urls.insert(0, alternate)
            else:
                alt = BeautifulSoup(get(alternate).content, 'html.parser')
                (REPORT / f'{doc_id}.gazette.html').write_bytes(str(alt).encode('utf-8'))
                links = [urljoin(alternate, a['data-href']) for a in alt.select('a.itemtep[data-href]') if not a['data-href'].lower().endswith('.doc')]
                urls = links + urls
        attempts = []
        for url in urls:
            try:
                response = get(url)
                if not response.content.startswith(b'%PDF-'):
                    raise ValueError('Not a PDF')
                pdf = pymupdf.open(stream=response.content, filetype='pdf')
                chars = [len(p.get_text('text', sort=True).strip()) for p in pdf]
                record = {'url':url, 'pages':len(pdf), 'native_text_chars':sum(chars), 'sparse_pages':[i+1 for i,c in enumerate(chars) if c<80]}
                attempts.append(record)
                if sum(chars) < 500 or sum(c >= 80 for c in chars) < len(chars)*0.8:
                    continue
                dest = ROOT / 'data/raw_data/additional_documents' / f'{doc_id}.pdf'
                dest.write_bytes(response.content)
                report.update(record)
                report.update({'pdf_path':dest.relative_to(ROOT).as_posix(), 'sha256':hashlib.sha256(response.content).hexdigest(), 'bytes':len(response.content), 'download_status':'downloaded'})
                break
            except Exception as exc:
                attempts.append({'url':url, 'error':str(exc)})
        else:
            report['download_status'] = 'needs_pdf_source'
        report['attempts'] = attempts
    except Exception as exc:
        report.update({'download_status':'error', 'error':str(exc)})
    print(doc_id, report['download_status'], report.get('pages'), report.get('native_text_chars'), flush=True)
    return report

def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, CANDIDATES))
    (REPORT/'downloads.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('Downloaded:',sum(x['download_status']=='downloaded' for x in results), '/ 13')

if __name__ == '__main__':
    main()
