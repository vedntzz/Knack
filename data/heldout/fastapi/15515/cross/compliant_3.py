from fastapi.sse import format_sse_event
def normalize_sse(src):
    a = src.replace("\r\n", "\n")
    b = a.replace("\r", "\n")
    return b.split("\n")
def build_payload_epsilon(data, note):
    d_lines = [f"data: {p}" for p in normalize_sse(data)]
    c_lines = [f": {q}" for q in normalize_sse(note)]
    return "\n".join(c_lines + d_lines + ["", ""]).encode()
print(build_payload_epsilon("x\r\ny\n", "c\rcomment"))
print(format_sse_event(data_str="x\r\ny\n", comment="c\rcomment"))