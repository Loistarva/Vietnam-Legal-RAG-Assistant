"""Conservative synthetic-fixture rules; not a complete PII detector."""
import re
from collections.abc import Mapping

SENSITIVE={'authorization','proxyauthorization','apikey','xapikey','token',
           'accesstoken','refreshtoken','password','passwd','secret','cookie',
           'setcookie','headers','environment','env','credentials'}


def _sensitive(key):
    normalized=re.sub(r'[^a-z0-9]','',str(key).lower())
    if normalized in {'tokenusage','inputtokens','outputtokens','totaltokens','prompttokens',
                      'completiontokens','cachedtokens','reasoningtokens'}:
        return False
    return normalized in SENSITIVE or any(word in normalized for word in ('secret','password','apikey','token','authorization'))


def mask_text(text,secrets=()):
    for secret in sorted((s for s in secrets if isinstance(s,str) and s),key=len,reverse=True):
        text=text.replace(secret,'[REDACTED]')
    text=re.sub(r'(?i)\bBearer\s+[^\s,;]+','Bearer [REDACTED]',text)
    text=re.sub(r'(?i)\b(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*[^\s,;]+','[REDACTED]',text)
    text=re.sub(r'\bsk-[A-Za-z0-9_-]+','[REDACTED]',text)
    text=re.sub(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b','[EMAIL]',text)
    text=re.sub(r'(?<!\w)(?:\+?84|0)(?:[ .-]?\d){9}(?!\d)','[PHONE]',text)
    text=re.sub(r'(?<!\w)(?:\d{12}|\d{9})(?!\w)','[ID]',text)
    return text


def mask(value,secrets=()):
    """Return a new JSON-safe value, removing sensitive keys recursively."""
    if isinstance(value,str):return mask_text(value,secrets)
    if isinstance(value,Mapping):
        return {mask_text(str(k),secrets):mask(v,secrets) for k,v in value.items() if not _sensitive(k)}
    if isinstance(value,(list,tuple)):return [mask(v,secrets) for v in value]
    if type(value) is int:
        masked=mask_text(str(value),secrets)
        return value if masked==str(value) else masked
    if value is None or type(value) in (bool,float):return value
    return '[UNSUPPORTED]'


def mask_external_payload(payload,secrets=()):
    """Opt-in hook for Dev 3 BEFORE an approved external call; not wired here."""
    return mask(payload,secrets)
