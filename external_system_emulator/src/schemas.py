from typing import Optional

from pydantic import BaseModel


class EventsConfig(BaseModel):
    event_type: str
    time_delay_seconds: int  # задержка перед отправкой события в секундах
    time_variation: int  # +- задержки в секундах
    probability: float  # вероятность отправки события (0.0 - 1.0)


class VariantConfig(BaseModel):
    feature_flag_value: str
    events: list[EventsConfig]
    # sub_events: list[EventsConfig] = []  # ивенты, зависящие от основных events


class ExperimentConfig(BaseModel):
    feature_flag_key: str  # ключ фичи из AB-системы
    time_delay_seconds: int  # задержка между запросами решений для разных пользователей
    time_variation: int  # +- задержки в секундах
    variants: list[VariantConfig]


class ScenarioConfig(BaseModel):
    scenario_name: str
    subjects_count: int  # количество разных пользователей
    experiment: ExperimentConfig


class ScenarioStatus(BaseModel):
    id: str
    scenario_name: str
    status: str  # pending, running, finished, error
    subjects_total: int
    subjects_processed: int
    events_sent: int
    errors: list[str] = []
