import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from ab_test_platform.src.core.settings import settings
from ab_test_platform.src.core.db_sql import (
    SQL_CREATE_MV,
    SQL_CREATE_IDX_EXPERIMENT_TYPE_TIME,
    SQL_CREATE_IDX_EXPERIMENT_VARIANT,
    SQL_REFRESH_MV,
    SQL_CREATE_FN_METRIC_SUMMARY,
    SQL_CREATE_FN_METRIC_TIMESERIES,
)
from ab_test_platform.src.infra.database.session import engine
from ab_test_platform.src.models.users import Users, UserRole
from ab_test_platform.src.models.feature_flags import FeatureFlags  # noqa: F401 — needed for metadata
from ab_test_platform.src.models.experiments import Experiments, ExperimentVersions, Variants  # noqa: F401 — needed for metadata
from ab_test_platform.src.models.approver_groups import ApproverGroups, ApproverGroupMembers  # noqa: F401 — needed for metadata
from ab_test_platform.src.models.metrics import Metrics, ExperimentMetrics  # noqa: F401 — needed for metadata
from ab_test_platform.src.models.guardrail_triggers import GuardrailTriggers  # noqa: F401 — needed for metadata

from ab_test_platform.src.infra.utils.hash_creator import HashCreator


async def add_super_admin(hash_creator: HashCreator, session: AsyncSession):
    # SQLModel.metadata.create_all(engine)
    res = await session.execute(
        select(Users).where(Users.email == settings.admin_email)
    )
    obj = res.scalar_one_or_none()
    if obj is None:
        user_id = str(uuid.uuid4())
        user_db = Users(
            id=user_id,
            email=settings.admin_email,
            password_hash=await hash_creator.create_hash(settings.admin_password),
            role=UserRole.ADMIN
        )
        session.add(user_db)
        await session.commit()
    await session.close()
    # print("добавлен")

async def drop_all_in_database():
    async with engine.begin() as conn:
        # Дропаем все MV и все функции в схеме public — иначе drop_all упадёт из-за зависимостей.
        # Имена не хардкодим: подчищаем всё что есть, включая старые версии.
        await conn.execute(text("""
            DO $$
            DECLARE r RECORD;
            BEGIN
                FOR r IN SELECT matviewname FROM pg_matviews WHERE schemaname = 'public' LOOP
                    EXECUTE 'DROP MATERIALIZED VIEW IF EXISTS ' || quote_ident(r.matviewname) || ' CASCADE';
                END LOOP;
                FOR r IN SELECT routine_name FROM information_schema.routines
                         WHERE routine_schema = 'public' AND routine_type = 'FUNCTION' LOOP
                    EXECUTE 'DROP FUNCTION IF EXISTS ' || quote_ident(r.routine_name) || ' CASCADE';
                END LOOP;
            END $$;
        """))
        await conn.run_sync(SQLModel.metadata.drop_all)  # в проде закомментировать!
        # await conn.run_sync(SQLModel.metadata.create_all)


async def create_tables_and_mv(db_engine=None) -> None:
    """Создать MV mv_events_enriched и хранимые функции fn_metric_summary/fn_metric_timeseries."""
    target = db_engine or engine
    async with target.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(text(SQL_CREATE_MV))
        await conn.execute(text(SQL_CREATE_IDX_EXPERIMENT_TYPE_TIME))
        await conn.execute(text(SQL_CREATE_IDX_EXPERIMENT_VARIANT))
        await conn.execute(text("DROP FUNCTION IF EXISTS fn_metric_summary CASCADE"))
        await conn.execute(text("DROP FUNCTION IF EXISTS fn_metric_timeseries CASCADE"))
        await conn.execute(text(SQL_CREATE_FN_METRIC_SUMMARY))
        await conn.execute(text(SQL_CREATE_FN_METRIC_TIMESERIES))


async def initial_mv_refresh(db_engine=None) -> None:
    """Первичное наполнение MV при старте сервиса."""
    target = db_engine or engine
    async with target.begin() as conn:
        await conn.execute(text(SQL_REFRESH_MV))
