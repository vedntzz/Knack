from fastapi.sse import _split_sse_lines, format_sse_event
def pack_remark_lines(remark: str) -> bytes:
    rows = [f": {bit}" for bit in _split_sse_lines(remark)]
    assert format_sse_event(comment=remark).startswith(b":")
    rows.extend(["", ""])
    return ("\n".join(rows) + "\n").encode("utf-8")