import uuid
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ErrorCode(Enum):
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    USER_INACTIVE = "USER_INACTIVE"
    DSL_PARSE_ERROR = "DSL_PARSE_ERROR"
    DSL_INVALID_FIELD = "DSL_INVALID_FIELD"
    DSL_INVALID_OPERATOR = "DSL_INVALID_OPERATOR"
    RULE_NAME_ALREADY_EXISTS = "RULE_NAME_ALREADY_EXISTS"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


class ApiError(BaseModel):
    code: ErrorCode
    message: str
    traceId: UUID = uuid.uuid4()
    timestamp: datetime
    path: str
    details: dict | None = None


class FieldError(BaseModel):
    field: str
    issue: str
    rejectedValue: object | None = None


class ValidationErrorResponse(BaseModel):
    code: str
    message: str
    traceId: UUID
    timestamp: datetime
    path: str
    fieldErrors: list[FieldError]


class AppException(Exception):
    status_code: int = 500
    error_code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR
    message: str = "Internal server error"
    details: dict | None = None

    def __init__(
        self,
        message: str | None = None,
        details: dict | None = None,
    ):
        if message:
            self.message = message
        self.details = details


class EmailAlreadyExistsError(AppException):
    status_code = 409
    error_code = ErrorCode.EMAIL_ALREADY_EXISTS
    message = "Email уже используется"


class UnauthorizedError(AppException):
    status_code = 401
    error_code = ErrorCode.UNAUTHORIZED
    message = "Токен отсутствует или невалиден"


class AccessDeniedError(AppException):
    status_code = 403
    error_code = ErrorCode.FORBIDDEN
    message = "Недостаточно прав для выполнения операции"


class UserInactiveError(AppException):
    status_code = 423
    error_code = ErrorCode.USER_INACTIVE
    message = "Пользователь деактивирован"


class BadRequestError(AppException):
    status_code = 400
    error_code = ErrorCode.BAD_REQUEST
    message = "Ошибка в данных запроса"


class UnsupportableContentError(AppException):
    status_code = 422
    error_code = ErrorCode.VALIDATION_FAILED
    message = "Некоторые поля не прошли валидацию"


class ConflictError(AppException):
    status_code = 409
    error_code = ErrorCode.CONFLICT
    message = "Операция конфликтует с текущим состоянием"


class EntityNotFoundError(AppException):
    status_code = 404
    error_code = ErrorCode.NOT_FOUND
    message = "Entity not found"


class EntityAlreadyExistsError(AppException):
    status_code = 409
    error_code = ErrorCode.CONFLICT
    message = "Entity already exists"
