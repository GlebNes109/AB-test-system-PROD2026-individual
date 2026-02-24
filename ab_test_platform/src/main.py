import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import uvicorn
from ab_test_platform.src.api.deps import get_hash_creator
from ab_test_platform.src.api.routes import (
    approve_groups,
    auth,
    decisions,
    events,
    experiments,
    feature_flags,
    metrics,
    reports,
    reviews,
    users,
)
from ab_test_platform.src.application.worker import guardrail_loop, mv_refresh_loop
from ab_test_platform.src.core.init_data import (
    add_super_admin,
    create_tables_and_mv,
    drop_all_in_database,
)
from ab_test_platform.src.core.settings import settings
from ab_test_platform.src.domain.exceptions import (
    ApiError,
    AppException,
    ErrorCode,
    FieldError,
    ValidationErrorResponse,
)
from ab_test_platform.src.infra.database.session import async_session_maker, engine
from ab_test_platform.src.infra.redis.session import get_redis_client
from fastapi import APIRouter, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_maker() as session:
        hash_creator = get_hash_creator()
        # await drop_all_in_database()
        if settings.drop_db_on_startup:
            await drop_all_in_database()
        await create_tables_and_mv()
        await add_super_admin(hash_creator, session)
    # await create_mv_and_functions()
    # await initial_mv_refresh()
    task_guardrail = asyncio.create_task(guardrail_loop(settings.guardrail_check_interval_seconds))
    task_mv = asyncio.create_task(mv_refresh_loop(settings.mv_refresh_interval_seconds))
    yield
    task_guardrail.cancel()
    task_mv.cancel()
    for task in (task_guardrail, task_mv):
        try:
            await task
        except asyncio.CancelledError:
            pass


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

app.include_router(api_router)
"""
@app.get("/demo-prod/drop-database", tags=["Ops"])
async def drop():
    
    hash_creator = get_hash_creator()
    await drop_all_in_database()
    await create_tables_and_mv()
    async with async_session_maker() as session:
        await add_super_admin(hash_creator, session)
"""


@app.get("/health", tags=["Ops"])
async def health():
    return {"status": "ok"}


@app.get("/ready", tags=["Ops"])
async def ready():
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"unavailable: {e}"

    try:
        redis = get_redis_client()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"unavailable: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not ready", "checks": checks},
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    trace_id = uuid4()

    if exc.error_code == ErrorCode.VALIDATION_FAILED and exc.status_code == 422:
        field_errors = exc.details.get("fieldErrors") if exc.details else []
        error = ValidationErrorResponse(
            code=ErrorCode.VALIDATION_FAILED,
            message=exc.message,
            traceId=trace_id,
            timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
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
            timestamp=datetime.now(UTC),
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
        timestamp=datetime.now(UTC),
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