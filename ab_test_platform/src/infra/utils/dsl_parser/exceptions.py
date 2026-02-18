class ParserError(Exception):
    code: str
    message: str
    def __init__(
        self,
        code: str | None = None,
        message: str | None = None,
    ):
        self.message = message
        self.code = code