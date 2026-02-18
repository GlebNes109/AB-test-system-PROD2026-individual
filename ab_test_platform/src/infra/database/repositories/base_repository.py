from sqlalchemy.exc import IntegrityError, NoResultFound
from typing import Type, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, asc, desc

from ab_test_platform.src.domain.exceptions import EntityNotFoundError, EntityAlreadyExistsError

from ab_test_platform.src.domain.interfaces.repositories.base_repository_interface import SortOrder, BaseRepositoryInterface
from ab_test_platform.src.models.models import ReadModelType, ModelType



class BaseRepository(BaseRepositoryInterface):
    def __init__(self, session: AsyncSession, model: Type[ModelType], read_schema: Type[ReadModelType]):
        self.session = session
        self.model = model
        self.read_schema = read_schema

    async def get(self, id: Any) -> ReadModelType:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        try:
            obj = result.scalar_one()
            return self.read_schema.model_validate(obj, from_attributes=True)
        except NoResultFound:
            raise EntityNotFoundError

    async def get_all(self, limit: int, offset: int, order_by: str | None = None, order: SortOrder = SortOrder.DESC) -> tuple[list[ReadModelType], int]:
        stmt = select(self.model).limit(limit).offset(offset)
        if order_by:
            column = getattr(self.model, order_by, None)
            if column is None:
                raise ValueError(f"Invalid order_by field: {order_by}")

            stmt = stmt.order_by(
                asc(column) if order == SortOrder.ASC else desc(column),
                asc(self.model.id)
            )
        else:
            stmt = stmt.order_by(asc(self.model.id))

        result = await self.session.execute(stmt)
        objs = result.scalars().all()
        count_stmt = select(func.count()).select_from(self.model)
        total = await self.session.scalar(count_stmt)
        return [self.read_schema.model_validate(obj, from_attributes=True) for obj in objs], total

    async def create(self, obj: ModelType) -> ReadModelType:
        db_obj = self.model(**obj.model_dump())
        # db_obj.id = str(uuid.uuid4())
        try:
            self.session.add(db_obj)
            await self.session.commit()
            await self.session.refresh(db_obj)
            return self.read_schema.model_validate(db_obj, from_attributes=True)
        except IntegrityError as e:
            if e.orig.sqlstate == '23505':
                raise EntityAlreadyExistsError from e
            else:
                raise

    async def update(self, obj: ModelType) -> ReadModelType:
        try:
            await self.session.execute(
                update(self.model)
                .where(self.model.id == obj.id)
                .values(**obj.model_dump(exclude_none=True))
            )
            await self.session.commit()
            return await self.get(obj.id)
        except IntegrityError as e:
            if e.orig.sqlstate == '23505':
                raise EntityAlreadyExistsError from e
            else:
                raise

    async def delete(self, id: Any) -> bool:
        await self.get(id) # проверка что существует (чтобы не удаляли по нескольку раз одно и то же)))
        await self.session.execute(delete(self.model).where(self.model.id == id))
        await self.session.commit()
        return True
