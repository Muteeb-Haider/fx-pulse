class FxPulseError(Exception):
    """Base error for all client failures."""


class ApiError(FxPulseError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(ApiError):
    pass


class RateLimitError(ApiError):
    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after
