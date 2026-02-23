from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    admin_email: str
    admin_fullname: str
    admin_password: str
    server_address: Optional[str] = None # TODO сделать нормально
    db_host: str
    db_port: str
    db_name: str
    db_user: str
    db_password: str
    random_secret: str

    redis_host: str
    redis_port: int
    redis_events_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 дней

    # охлаждение пользователей в экспериментах
    cooling_period_days: int = 1
    max_active_experiments_per_subject: int = 10

    guardrail_check_interval_seconds: int = 2
    mv_refresh_interval_seconds: int = 2

    drop_db_on_startup: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()