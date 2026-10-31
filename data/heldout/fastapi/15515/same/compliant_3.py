from fastapi.sse import ServerSentEvent
class TrailKeeper:
    def emit_payload(self, blob: str) -> bytes:
        evt = ServerSentEvent(raw_data=blob)
        assert evt.raw_data is not None
        normalized = evt.raw_data.replace("\r\n", "\n").replace("\r", "\n")
        parts = normalized.split("\n")
        encoded = []
        for p in parts:
            encoded.append(f"data: {p}")
        encoded.extend(["", ""])
        return "\n".join(encoded).encode("utf-8")