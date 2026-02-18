from pydantic import BaseModel

class EventsConfig(BaseModel):
    event_type: str
    probability: float # вероятность присылания данного события при этом значении флага


class VariantConfig(BaseModel):
    feature_flag_value: str
    events: list[EventsConfig]

class ExperimentConfig(BaseModel):
    feature_flag_key: str  # запрашиваемая фича из кор системы
    variants: list[VariantConfig]


class ScenarioConfig(BaseModel):
    scenario_name: str
    subjects_count: str # количество разных пользователей
    # feature_flag_key: str # запрашиваемая фича из кор системы
    experiment: ExperimentConfig
