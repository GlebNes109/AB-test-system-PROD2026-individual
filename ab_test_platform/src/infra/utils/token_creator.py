from datetime import datetime, timezone

import jwt

from ab_test_platform.src.domain.exceptions import UnauthorizedError
from ab_test_platform.src.domain.interfaces.token_creator_interface import TokenCreatorInterface
from ab_test_platform.src.infra.database.repositories.user_repository import UserRepository


class TokenCreator(TokenCreatorInterface):
    def __init__(self, secret_key, algorithm, repository: UserRepository):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.repository = repository

    """async def create_refresh_token(self, user_id: str) -> str:
        expire = int(datetime.now(timezone.utc).timestamp()) + 3600
        to_encode = {"sub": user_id, "exp": expire, "type": "refresh"}
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)"""

    async def create_access_token(self, user_id: str) -> tuple[str, int]:
        user = await self.repository.get(user_id)
        now = int(datetime.now(timezone.utc).timestamp())
        expire = now + 3600
        to_encode = {
            "sub": user_id,
            "role": user.role.value,
            "iat": now,
            "exp": expire
        }
        token = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return token, expire

    async def verify_access_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("sub")
            if not await self.repository.get(user_id):
                raise jwt.PyJWTError
            return user_id

        except jwt.PyJWTError:
            raise UnauthorizedError
