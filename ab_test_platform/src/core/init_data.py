import uuid

from ab_test_platform.src.core.db_sql import (
    SQL_CREATE_FN_METRIC_SUMMARY,
    SQL_CREATE_FN_METRIC_TIMESERIES,
    SQL_CREATE_IDX_EXPERIMENT_TYPE_TIME,
    SQL_CREATE_IDX_EXPERIMENT_VARIANT,
    SQL_CREATE_MV,
    SQL_REFRESH_MV,
)
from ab_test_platform.src.core.settings import settings
from ab_test_platform.src.infra.database.session import engine
from ab_test_platform.src.infra.utils.hash_creator import HashCreator
from ab_test_platform.src.models.approver_groups import (  # noqa: F401 — needed for metadata
    ApproverGroupMembers,
    ApproverGroups,
)
from ab_test_platform.src.models.experiments import (  # noqa: F401 — needed for metadata
    Experiments,
    ExperimentVersions,
    Variants,
)
from ab_test_platform.src.models.feature_flags import (
    FeatureFlags,  # noqa: F401 — needed for metadata
)
from ab_test_platform.src.models.guardrail_triggers import (
    GuardrailTriggers,  # noqa: F401 — needed for metadata
)
from ab_test_platform.src.models.metrics import (  # noqa: F401 — needed for metadata
    ExperimentMetrics,
    Metrics,
)
from ab_test_platform.src.models.users import UserRole, Users
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select


async def add_super_admin(hash_creator: HashCreator, session: AsyncSession):
    # SQLModel.metadata.create_all(engine)
    res = await session.execute(select(Users).where(Users.email == settings.admin_email))
    obj = res.scalar_one_or_none()
    if obj is None:
        user_id = str(uuid.uuid4())
        user_db = Users(
            id=user_id,
            email=settings.admin_email,
            password_hash=await hash_creator.create_hash(settings.admin_password),
            role=UserRole.ADMIN,
        )
        session.add(user_db)
        await session.commit()
    await session.close()
    # print("добавлен")


async def drop_all_in_database():
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$
            DECLARE r RECORD;
            BEGIN
                FOR r IN SELECT matviewname FROM pg_matviews WHERE schemaname = 'public' LOOP
                    EXECUTE 'DROP MATERIALIZED VIEW IF EXISTS ' || quote_ident(r.matviewname) || ' CASCADE';
                END LOOP;
                FOR r IN SELECT p.proname
                         FROM pg_proc p
                         JOIN pg_namespace n ON n.oid = p.pronamespace
                         WHERE n.nspname = 'public'
                           AND NOT EXISTS (
                               SELECT 1 FROM pg_depend d
                               WHERE d.objid = p.oid AND d.deptype = 'e'
                           )
                LOOP
                    EXECUTE 'DROP FUNCTION IF EXISTS ' || quote_ident(r.proname) || ' CASCADE';
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
