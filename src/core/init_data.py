import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from src.core.settings import settings
from src.infra.database.session import engine
from src.models.users import Users, UserRole
from src.models.feature_flags import FeatureFlags  # noqa: F401 — needed for metadata
from src.models.experiments import Experiments, ExperimentVersions, Variants  # noqa: F401 — needed for metadata
from src.models.approver_groups import ApproverGroups, ApproverGroupMembers  # noqa: F401 — needed for metadata

from src.infra.utils.hash_creator import HashCreator


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

async def create_tables(db_engine=None):
    if db_engine:
        async with db_engine.begin() as conn:
            # await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
    else:
        async with engine.begin() as conn:
            # await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
