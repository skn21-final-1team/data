from core.exceptions.base import CustomException


class CrawlFailedError(CustomException):
    def __init__(self, message: str = "크롤링에 실패했습니다."):
        super().__init__(message, code=422)


class RobotsBlockedError(CrawlFailedError):
    def __init__(self, message: str = "robots.txt에 의해 차단된 URL입니다."):
        super().__init__(message)


class ContentTooShortError(CrawlFailedError):
    def __init__(self, message: str = "콘텐츠가 너무 짧습니다."):
        super().__init__(message)


class GarbageContentError(CrawlFailedError):
    def __init__(self, message: str = "유효하지 않은 콘텐츠가 감지되었습니다."):
        super().__init__(message)


class ScrapeFetchError(CrawlFailedError):
    def __init__(self, message: str = "페이지를 가져오는 데 실패했습니다."):
        super().__init__(
            message,
        )
