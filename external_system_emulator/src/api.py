import asyncio

from fastapi import APIRouter, HTTPException
from starlette import status

from src.schemas import ScenarioConfig, ScenarioStatus
from src.service import ScenarioStore, ScenarioRunner

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_store: ScenarioStore | None = None
_runner: ScenarioRunner | None = None


def init_dependencies(store: ScenarioStore, runner: ScenarioRunner):
    global _store, _runner
    _store = store
    _runner = runner


@router.post("", summary="Создать сценарий", status_code=status.HTTP_201_CREATED)
async def create_scenario(config: ScenarioConfig) -> ScenarioStatus:
    return _store.create(config)


@router.post("/{scenario_id}/run", summary="Запустить сценарий")
async def run_scenario(scenario_id: str) -> ScenarioStatus:
    s = _store.get_status(scenario_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if s.status != "pending":
        raise HTTPException(status_code=400, detail=f"Scenario already {s.status}")
    asyncio.create_task(_runner.run(scenario_id))
    s.status = "starting"
    return s


@router.get("/{scenario_id}", summary="Статус сценария")
async def get_scenario(scenario_id: str) -> ScenarioStatus:
    s = _store.get_status(scenario_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return s


@router.get("", summary="Список всех сценариев")
async def list_scenarios() -> list[ScenarioStatus]:
    return _store.list_all()
