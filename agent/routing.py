"""Conservative scope routing; rules are not a calibrated intent classifier."""
import re
import unicodedata
from dataclasses import dataclass


def folded(text):
    text=unicodedata.normalize('NFD',text.casefold().replace('đ','d'))
    return ' '.join(''.join(c for c in text if unicodedata.category(c)!='Mn').split())


@dataclass(frozen=True)
class Route:
    kind: str
    reason: str
    message: str = ''


def route_query(query, known_numbers=()):
    if not isinstance(query,str) or not query.strip():
        raise ValueError('Require a nonempty question')
    text=folded(query)
    domain=any(re.search(r'\b'+re.escape(phrase)+r'\b',text) for phrase in ('hon nhan','ket hon','ly hon','vo chong','vo toi','chong toi',
        'nuoi con','cap duong','mang thai ho','cha me','con chung','con nuoi','tai san chung','tai san rieng',
        'nhan con','nhan cha','nhan me','xac dinh cha','xac dinh me','quyen cua con'))
    referenced=any(re.search(r'(?<![\w/])'+re.escape(folded(number))+r'(?![\w/-])',text) for number in known_numbers)
    other=any(re.search(r'\b'+re.escape(p)+r'\b',text) for p in ('thue','giao thong','hinh su','lao dong','doanh nghiep'))
    if other:
        if domain:
            return Route('clarify','mixed_scope','Bạn muốn hỏi về quan hệ hôn nhân/gia đình hay lĩnh vực pháp luật khác trong tình huống này?')
        return Route('out_of_scope','unsupported_legal_domain','Mình hiện hỗ trợ tra cứu hôn nhân và gia đình. Bạn có câu hỏi trong phạm vi này không?')
    if re.search(r'(tai thoi diem|con hieu luc (?:vao )?nam|quy dinh truoc (?:ngay|nam)|luat ap dung nam)\b',text):
        return Route('clarify','historical_validity_unavailable','Mình chưa xác minh được hiệu lực theo thời điểm lịch sử. Bạn muốn tra cứu văn bản cụ thể hay quy định hiện hành?')
    vague={'ly hon','ket hon','cap duong','nuoi con','tai san chung','hon nhan','tu van phap luat','toi co duoc khong','giup toi'}
    if text.strip(' .?!') in vague:
        return Route('clarify','missing_subject','Bạn muốn làm rõ điều kiện, thủ tục hay quyền và nghĩa vụ nào? Hãy nêu câu hỏi cụ thể hơn.')
    if domain or referenced:
        return Route('legal','supported_scope')
    if re.fullmatch(r'(xin chao|chao(?: ban)?|hello|hi|cam on(?: ban)?|tam biet)[!.\s]*',text):
        return Route('general','social_fast_path','Chào bạn! Mình hỗ trợ tra cứu quy định về hôn nhân và gia đình.')
    if any(p in text for p in ('phap luat','nghi dinh','nghi quyet','dieu luat','toa an')):
        return Route('clarify','legal_scope_unclear','Bạn đang hỏi vấn đề nào về hôn nhân và gia đình, hoặc văn bản cụ thể nào?')
    return Route('general','nonlegal_fast_path','Mình hỗ trợ tra cứu hôn nhân và gia đình. Bạn có câu hỏi pháp lý nào trong phạm vi này?')
