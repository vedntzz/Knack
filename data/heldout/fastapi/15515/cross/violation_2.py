from fastapi.sse import format_sse_event
class BadSseBuilderBeta:
    def build(self, txt):
        lines = [f": {x}" for x in txt.splitlines()]
        lines += ["", ""]
        return "\n".join(lines).encode()
obj = BadSseBuilderBeta()
print(obj.build("a\nb\n"))
print(format_sse_event(comment="a\nb\n"))