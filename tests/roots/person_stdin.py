import io


class Stdin(io.StringIO):
    # A stand-in stdin that is, or is not, an interactive terminal.
    def __init__(self, tty: bool) -> None:
        super().__init__()
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty
