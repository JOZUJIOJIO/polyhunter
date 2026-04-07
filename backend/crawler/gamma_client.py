import json

import httpx

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


class GammaClient:
    def __init__(self, base_url: str = GAMMA_BASE_URL):
        self.base_url = base_url

    async def fetch_active_events(self, limit: int = 100, offset: int = 0) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/events",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "offset": offset,
                    "order": "volume24hr",
                    "ascending": "false",
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    def parse_markets(self, event: dict) -> list[dict]:
        results = []
        for m in event.get("markets", []):
            try:
                clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                prices = json.loads(m.get("outcomePrices", "[]"))
            except (json.JSONDecodeError, TypeError):
                continue

            if len(clob_ids) < 2 or len(prices) < 2:
                continue

            tags = m.get("tags", [])
            category = tags[0]["label"] if tags else None

            results.append({
                "id": m["id"],
                "condition_id": m.get("conditionId", ""),
                "token_id_yes": clob_ids[0],
                "token_id_no": clob_ids[1],
                "question": m.get("question", ""),
                "slug": m.get("slug", ""),
                "category": category,
                "end_date": m.get("endDate"),
                "active": m.get("active", True) and not m.get("closed", False),
                "last_price_yes": float(prices[0]),
                "last_price_no": float(prices[1]),
                "volume_24h": float(m.get("volume", 0)),
                "liquidity": float(m.get("liquidityClob", 0)),
            })
        return results
