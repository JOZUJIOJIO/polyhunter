"""Price monitor API routes."""

from fastapi import APIRouter

router = APIRouter(prefix="/monitor", tags=["monitor"])

# Monitor state is managed by the trading scripts, not the API.
# These endpoints provide read-only status.

_monitor_status = {"running": False, "symbols": [], "exchange": ""}


def update_monitor_status(running: bool, symbols: list[str], exchange: str):
    _monitor_status["running"] = running
    _monitor_status["symbols"] = symbols
    _monitor_status["exchange"] = exchange


@router.get("/status")
async def get_status():
    return _monitor_status
