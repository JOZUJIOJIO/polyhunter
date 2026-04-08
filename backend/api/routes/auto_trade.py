import json
import os

from fastapi import APIRouter

from backend.api.schemas import AutoTradeSettings

router = APIRouter()

SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "auto_trade_config.json",
)

DEFAULTS = {
    "enabled": False,
    "min_confidence": 70,
    "min_edge_pct": 5.0,
    "size_usd": 5.0,
}


def _load() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return dict(DEFAULTS)


def _save(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/auto-trade", response_model=AutoTradeSettings)
def get_auto_trade_settings():
    return _load()


@router.post("/auto-trade", response_model=AutoTradeSettings)
def update_auto_trade_settings(req: AutoTradeSettings):
    data = req.model_dump()
    _save(data)
    return data
