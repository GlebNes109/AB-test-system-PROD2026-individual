import os
import logging

import uvicorn
from fastapi import FastAPI

from src.abtests_api_integration import ABTestClient
from src.service import ScenarioStore, ScenarioRunner
from src.api import router, init_dependencies

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

ROOT_PATH = os.getenv("ROOT_PATH", "")
app = FastAPI(title="External System Emulator", version="0.1.0", root_path=ROOT_PATH)

AB_PLATFORM_URL = os.getenv("AB_PLATFORM_URL", "http://localhost:8080")

client = ABTestClient(base_url=AB_PLATFORM_URL)
store = ScenarioStore()
runner = ScenarioRunner(client=client, store=store)

init_dependencies(store, runner)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8090"))
    uvicorn.run(app, host=host, port=port)
