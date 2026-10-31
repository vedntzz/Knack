from fastapi.sse import ServerSentEvent
def build_wire_blurb(payload: str) -> bytes:
    evt = ServerSentEvent(raw_data=payload)
    assert evt.raw_data is not None
    wire = []
    for chunk in evt.raw_data.splitlines():
        wire.append(f"data: {chunk}")
    wire.append("")
    wire.append("")
    return "\n".join(wire).encode("utf-8")