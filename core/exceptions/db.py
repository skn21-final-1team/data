from core.exceptions.pipeline import PipelineStageError


class SourceSaveError(PipelineStageError):
    stage = "db"

    def __init__(self, message: str = "source 저장에 실패했습니다."):
        super().__init__(message)


class RefinedSaveError(SourceSaveError):
    def __init__(self, message: str = "refined 저장에 실패했습니다."):
        super().__init__(message)


class SummarySaveError(SourceSaveError):
    def __init__(self, message: str = "summary 저장에 실패했습니다."):
        super().__init__(message)


class PageDataSaveError(PipelineStageError):
    stage = "db"

    def __init__(self, message: str = "PGVector 적재에 실패했습니다."):
        super().__init__(message)
