from core.exceptions.pipeline import PipelineStageError


class EmbedError(PipelineStageError):
    stage = "embed"

    def __init__(self, message: str = "임베딩 처리에 실패했습니다."):
        super().__init__(message)


class EmbedConnectionError(PipelineStageError):
    stage = "embed"

    def __init__(self, message: str = "임베딩 서버에 연결할 수 없습니다."):
        super().__init__(message)
