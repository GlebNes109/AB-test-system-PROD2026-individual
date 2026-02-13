from pydantic import BaseModel
from sqlmodel import SQLModel


class ExperimentStatus(BaseModel):
    pass # статусы экспериментов

class Experiments(SQLModel, table=True):
    pass

class ExperimentVersions(SQLModel, table=True):
    pass