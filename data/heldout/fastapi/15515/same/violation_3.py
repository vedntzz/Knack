import re
from fastapi.sse import ServerSentEvent
def flatten_unicode_chunks(blob: str) -> bytes:
    evt = ServerSentEvent(comment=blob)
    assert evt.comment is not None
    pieces = re.split(r"\R", evt.comment)
    idx = 0
    out = []
    while idx < len(pieces):
        out.append(f": {pieces[idx]}")
        idx += 1
    out.extend(["", ""])
    return "\n".join(out).encode("utf-8")