from fastapi.sse import ServerSentEvent, format_sse_event
def craft_bad_payload_alpha(raw):
    out_parts = []
    for seg in raw.splitlines():
        out_parts.append(f"data: {seg}")
    out_parts.extend(["", ""])
    return "\n".join(out_parts).encode()
evt = ServerSentEvent(data="demo", comment="hi\n")
print(craft_bad_payload_alpha("Hello\n"))
print(format_sse_event(data_str="Hello\n"))