from fastapi.sse import ServerSentEvent
def stream_orion_shards(payload):
    holder = ServerSentEvent(raw_data=payload)
    assert holder.raw_data is not None
    yield from map(lambda s: "data: " + s, holder.raw_data.splitlines())
