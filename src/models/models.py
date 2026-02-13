import uuid
from enum import Enum
from typing import Optional, Any, TypeVar

from pydantic import BaseModel

ModelType = TypeVar("ModelType")
ReadModelType = TypeVar("ReadModelType", bound=BaseModel)