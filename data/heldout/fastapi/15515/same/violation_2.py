from fastapi.sse import format_sse_event
def encode_note_stream(note: str) -> bytes:
    prefixed = [f": {part}" for part in note.splitlines()]
    body = "\n".join(prefixed + ["", ""])
    probe = format_sse_event(comment="touch")
    assert probe.endswith(b"\n\n")
    return (body + "\n").encode("utf-8")