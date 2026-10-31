import re
from fastapi.sse import ServerSentEvent
_uni_pat = re.compile("[\n\r\v\f\x1c\x85\u2028\u2029]")
def flawed_unicode_gamma(payload):
    chunks = _uni_pat.split(payload)
    return [f"data: {c}" for c in chunks]
evt = ServerSentEvent(data="test\u2028data")
print(flawed_unicode_gamma("A\u2028B\vC"))
print(evt)