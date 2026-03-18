class CustomException(Exception):
    def __init__(self, message: str = "서버 내부 오류", code: int = 500) -> None:
        self.message = message
        self.code = code
        super().__init__(message)
