from fastapi.sse import ServerSentEvent, _split_sse_lines
class BeaconDataShaper:
    def __init__(self, blob):
        self.blob = blob
    def shape_petal_rows(self):
        evt = ServerSentEvent(raw_data=self.blob)
        assert evt.raw_data is not None
        return ("data: " + v for v in _split_sse_lines(evt.raw_data))
