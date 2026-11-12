"""Shared metadata predicates; explicit query references, not legal date reasoning."""
import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import date


def normalized(value):
    return unicodedata.normalize('NFC', str(value or '')).strip().casefold()


def document_number(value):
    value = unicodedata.normalize('NFC', str(value or '')).strip().upper()
    value = re.sub(r'[‐‑–—]', '-', value)
    return value.replace('ND-CP', 'NĐ-CP').replace('NQ-HDTP', 'NQ-HĐTP')


@dataclass(frozen=True)
class RetrievalPolicy:
    validity_mode: str = 'current_only'
    document_numbers: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    issue_year: int | None = None

    def __post_init__(self):
        if self.validity_mode not in ('current_only', 'exclude_expired'):
            raise ValueError('Unsupported validity mode; historical validity is not inferred')
        if self.issue_year is not None and (type(self.issue_year) is not int or not 1800 <= self.issue_year <= 2200):
            raise ValueError('Invalid issue year')
        if not isinstance(self.document_numbers,(tuple,list)) or not isinstance(self.document_types,(tuple,list)):
            raise ValueError('Document filters must be tuples/lists, not strings')
        if any(not isinstance(v, str) or not v.strip() for v in (*self.document_numbers, *self.document_types)):
            raise ValueError('Empty/invalid document filter')
        object.__setattr__(self,'document_numbers',tuple(document_number(n) for n in self.document_numbers))
        object.__setattr__(self,'document_types',tuple(t.strip() for t in self.document_types))

    def matches(self, metadata):
        status = normalized(metadata.get('validity_status'))
        if self.validity_mode == 'current_only' and status != normalized('Còn hiệu lực'):
            return False
        if self.validity_mode == 'exclude_expired' and status in {normalized('Hết hiệu lực'), normalized('Hết hiệu lực toàn bộ')}:
            return False
        if self.document_numbers and document_number(metadata.get('document_number')) not in {document_number(n) for n in self.document_numbers}:
            return False
        if self.document_types and normalized(metadata.get('document_type')) not in {normalized(t) for t in self.document_types}:
            return False
        if self.issue_year is not None:
            value = str(metadata.get('issue_date') or '')
            try:
                issued = date.fromisoformat(value)
            except ValueError:
                return False
            if issued.year != self.issue_year:
                return False
        return True

    def to_dict(self):
        return asdict(self)


def policy_from_query(query):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Empty query')
    text = unicodedata.normalize('NFC', query)
    text = re.sub(r'[‐‑–—]', '-', text)
    numbers = tuple(dict.fromkeys(document_number(m.group()) for m in re.finditer(
        r'(?<!\w)\d{1,5}/(?:19|20)\d{2}/[A-ZĐ][A-ZĐ0-9]*(?:-[A-ZĐ0-9]+)*', text, re.I)))
    types = []
    for label in ('Nghị định', 'Nghị quyết', 'Thông tư'):
        if re.search(r'(?<!\w)' + label + r'(?!\w)', text, re.I):
            types.append(label)
    # 'pháp luật', 'điều luật' and generic 'theo luật' are not document-type filters.
    if re.search(r'(?<!\w)quyết định\s+(?:số\b|\d{1,5}/)', text, re.I):
        types.append('Quyết định')
    law_matches = list(re.finditer(r'(?<!\w)luật\s+(?:số\b|hôn nhân\b|\d|ban hành\b)',text,re.I))
    if any(not re.search(r'pháp\s*$',text[:m.start()],re.I) for m in law_matches):
        types.append('Luật')
    year_match = re.search(r'ban hành\s+(?:(?:vào|trong)\s+)?năm\s+((?:19|20)\d{2})\b', text, re.I)
    return RetrievalPolicy(document_numbers=numbers, document_types=tuple(types),
                           issue_year=int(year_match.group(1)) if year_match else None)
