from typing import TypeVar

from pydantic import BaseModel

ModelType = TypeVar("ModelType")
ReadModelType = TypeVar("ReadModelType", bound=BaseModel)
