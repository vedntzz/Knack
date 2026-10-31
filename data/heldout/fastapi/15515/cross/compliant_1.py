from fastapi.sse import _split_sse_lines, format_sse_event
def proper_renderer_one(src):
    buf = []
    for piece in _split_sse_lines(src):
        buf.append(f"data: {piece}")
    buf.extend(["", ""])
    return "\n".join(buf).encode()
print(proper_renderer_one("Hello\r\nWorld\rTest\n"))
print(format_sse_event(data_str="Hello\r\nWorld"))