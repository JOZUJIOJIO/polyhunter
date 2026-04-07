import httpx

CLOB_BASE_URL = "https://clob.polymarket.com"


class ClobClient:
    def __init__(self, base_url: str = CLOB_BASE_URL):
        self.base_url = base_url

    def _check_status(self, resp: httpx.Response) -> None:
        """Raise HTTPStatusError for non-2xx responses, compatible with mocked responses."""
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code}",
                request=resp.request if resp.request is not None else httpx.Request("GET", self.base_url),
                response=resp,
            )

    async def get_order_book(self, token_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/book",
                params={"token_id": token_id},
                timeout=15,
            )
            self._check_status(resp)
            return resp.json()

    async def get_price(self, token_id: str, side: str = "buy") -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/price",
                params={"token_id": token_id, "side": side},
                timeout=15,
            )
            self._check_status(resp)
            data = resp.json()
            return float(data.get("price", 0))

    async def get_midpoint(self, token_id: str) -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/midpoint",
                params={"token_id": token_id},
                timeout=15,
            )
            self._check_status(resp)
            data = resp.json()
            return float(data.get("mid", 0))

    async def get_spread(self, token_id: str) -> float:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/spread",
                params={"token_id": token_id},
                timeout=15,
            )
            self._check_status(resp)
            data = resp.json()
            return float(data.get("spread", 0))

    async def get_prices_batch(self, token_ids: list[str]) -> dict[str, float]:
        results = {}
        async with httpx.AsyncClient() as client:
            for token_id in token_ids:
                try:
                    resp = await client.get(
                        f"{self.base_url}/midpoint",
                        params={"token_id": token_id},
                        timeout=15,
                    )
                    self._check_status(resp)
                    data = resp.json()
                    results[token_id] = float(data.get("mid", 0))
                except (httpx.HTTPError, ValueError):
                    continue
        return results
