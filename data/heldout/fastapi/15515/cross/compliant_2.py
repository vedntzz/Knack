from fastapi.sse import ServerSentEvent
class GoodSseBuilderDelta:
    def encode_comment(self, txt):
        norm = txt.replace("\r\n", "\n").replace("\r", "\n")
        return [f": {part}" for part in norm.split("\n")]
obj = GoodSseBuilderDelta()
print(obj.encode_comment("hi\r\nthere\rnow"))
print(ServerSentEvent(comment="hi\r\nthere"))