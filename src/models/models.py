import uuid
from enum import Enum
from typing import Optional, Any, TypeVar

from pydantic import BaseModel, model_validator, validator, field_validator

ModelType = TypeVar("ModelType")
UpdateModelType = TypeVar("UpdateModelType", bound=BaseModel)
ReadModelType = TypeVar("ReadModelType", bound=BaseModel)