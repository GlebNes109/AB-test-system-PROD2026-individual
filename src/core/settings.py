from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

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

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()