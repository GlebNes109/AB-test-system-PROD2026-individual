from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from ab_test_platform.src.api.deps import get_hash_creator
from ab_test_platform.src.api.routes import reports, feature_flags, decisions, experiments, auth, approve_groups, \
    events, users, reviews, metrics
from ab_test_platform.src.domain.exceptions import AppException, ApiError, ErrorCode, ValidationErrorResponse, FieldError
from ab_test_platform.src.core.init_data import create_tables, add_super_admin
from ab_test_platform.src.core.settings import settings
from ab_test_platform.src.infra.database.session import async_session_maker


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_maker() as session:
        hash_creator = get_hash_creator()
        await create_tables()
        await add_super_admin(hash_creator, session)
    yield


app = FastAPI(
    lifespan=lifespan,
    swagger_ui_init_oauth={},
    swagger_ui_parameters={"persistAuthorization": True},
)



api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(feature_flags.router, prefix="/feature-flags", tags=["Feature Flags"])
api_router.include_router(experiments.router, prefix="/experiments", tags=["Experiments"])
api_router.include_router(approve_groups.router, prefix="/users", tags=["Approver Groups"])
api_router.include_router(reviews.router, prefix="", tags=["Reviews"])
api_router.include_router(decisions.router, prefix="", tags=["Decisions"])
api_router.include_router(events.router, prefix="/events", tags=["Events"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
api_router.include_router(reports.router, prefix="/experiments", tags=["Reports"])

@api_router.get("/ping")
def send():
    return {"status": "ok"}

app.include_router(api_router)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    trace_id = uuid4()

    if exc.error_code == ErrorCode.VALIDATION_FAILED and exc.status_code == 422:
        field_errors = exc.details.get("fieldErrors") if exc.details else []
        error = ValidationErrorResponse(
            code=ErrorCode.VALIDATION_FAILED,
            message=exc.message,
            traceId=trace_id,
            timestamp=datetime.now(timezone.utc),
            path=request.url.path,
            fieldErrors=[FieldError(**fe) for fe in field_errors],
        )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(error),
        )

    error = ApiError(
        code=exc.error_code,
        message=exc.message,
        traceId=trace_id,
        timestamp=datetime.now(timezone.utc),
        path=request.url.path,
        details=exc.details,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    def bad_request_response(message: str) -> JSONResponse:
        error = ApiError(
            code=ErrorCode.BAD_REQUEST,
            message=message,
            traceId=uuid4(),
            timestamp=datetime.now(timezone.utc),
            path=request.url.path,
            details=None,
        )
        return JSONResponse(
            status_code=400,
            content=jsonable_encoder(error),
        )

    errors = exc.errors()
    error_types = {err.get("type", "") for err in errors}
    is_json_invalid = any(
        err_type.startswith("json_") or err_type == "value_error.jsondecode"
        for err_type in error_types
    )
    has_body_error = any("body" in err.get("loc", []) for err in errors)
    content_type = (request.headers.get("content-type") or "").lower()

    if is_json_invalid:
        return bad_request_response("Невалидный JSON")

    if has_body_error and content_type and not content_type.startswith("application/json"):
        return bad_request_response("Неподдерживаемый Content-Type")

    field_errors = []
    for err in errors:
        loc = ".".join([str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")])
        field_errors.append({
            "field": loc or "request",
            "issue": err.get("msg", "Invalid value"),
            "rejectedValue": err.get("input"),
        })

    error = ValidationErrorResponse(
        code=ErrorCode.VALIDATION_FAILED,
        message="Некоторые поля не прошли валидацию",
        traceId=uuid4(),
        timestamp=datetime.now(timezone.utc),
        path=request.url.path,
        fieldErrors=[FieldError(**fe) for fe in field_errors],
    )

    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(error),
    )

if __name__ == "__main__":
    server_address = settings.server_address
    host, port = server_address.split(":")
    uvicorn.run(app, host=host, port=int(port))