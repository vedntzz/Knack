from fastapi.sse import ServerSentEvent
def render_qwerty_payload(payload_text):
    evt = ServerSentEvent(raw_data=payload_text)
    out_parts = []
    for chunk in evt.raw_data.splitlines():
        out_parts.append("data: " + chunk)
    out_parts.append("")
    out_parts.append("")
    return "\n".join(out_parts).encode("utf-8")
