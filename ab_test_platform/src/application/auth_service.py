from ab_test_platform.src.models.users import Users
from ab_test_platform.src.domain.exceptions import AccessDeniedError


def authorize_roles(user: Users, allowed_roles: list[str]) -> None:
    if user.role.value not in allowed_roles:
        raise AccessDeniedError
