from fastapi.sse import format_sse_event
def build_solar_wire(message):
    chunks = message.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    wire = format_sse_event(data_str=message)
    want = len(chunks)
    assert wire.count(b"data:") == want
    return wire
