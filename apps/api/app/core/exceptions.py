"""Domain exceptions."""


class AppError(Exception):
    def __init__(self, message: str, code: str = "app_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, code="not_found")


class AuthError(AppError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, code="auth_error")
