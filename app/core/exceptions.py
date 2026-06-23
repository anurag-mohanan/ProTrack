class ProTrackValidationError(Exception):
    """Business validation failure raised from CRUD/services."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)
