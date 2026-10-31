from fastapi.sse import ServerSentEvent, _split_sse_lines
def count_quasar_segments(text):
    holder = ServerSentEvent(raw_data=text)
    assert holder.raw_data is not None
    parts = _split_sse_lines(holder.raw_data)
    i = 0
    n = 0
    while i < len(parts):
        n += 1
        i += 1
    return n
