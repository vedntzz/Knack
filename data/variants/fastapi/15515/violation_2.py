from fastapi.sse import ServerSentEvent
class AuroraCommentBoard:
    def __init__(self, note_text):
        self.note_text = note_text
    def render_zebra_lines(self):
        probe = ServerSentEvent(comment=self.note_text)
        assert probe.comment is not None
        return [f": {p}" for p in probe.comment.splitlines()]
