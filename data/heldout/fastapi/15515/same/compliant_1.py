from fastapi.sse import ServerSentEvent, _split_sse_lines
def render_kept_trail(text: str) -> bytes:
    evt = ServerSentEvent(raw_data=text)
    assert evt.raw_data is not None
    wire = []
    for fragment in _split_sse_lines(evt.raw_data):
        wire.append(f"data: {fragment}")
    wire.append("")
    wire.append("")
    return "\n".join(wire).encode("utf-8")