from enum import Enum
from typing import Optional, List

from pydantic import BaseModel


class MetricsType(Enum):
    PRIMARY = "PRIMARY"
    GUARDRAIL = "GUARGRAIL"

class Variants(BaseModel):
    name: str
    value: any # TODO проверить, что оно совпадает по типу с тем , что указано в feature flag
    weight: int
    is_control: Optional[bool] = False


class ExperimentMetrics:
    metric_id: str
    type: MetricsType
    threshold: Optional[str]
    window_minutes: Optional[str]
    action: Optional[str]
    # TODO threshold window_minutes и action задаются обязательно если MetricsType == GUARDRAIL и не задаются в ином случае


class ExperimentsCreate(BaseModel):
    feature_flag_id: str
    name: str
    targeting_rule: str
    audience_percentage: int
    variants: Variants
    metrics: List[ExperimentMetrics]



