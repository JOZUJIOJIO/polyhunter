from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.crawler.gamma_client import GammaClient
from backend.db.models import Market


class MarketCrawler:
    def __init__(self, session: Session, gamma_client: GammaClient | None = None):
        self.session = session
        self.gamma = gamma_client or GammaClient()

    async def _fetch_all_events(self, max_pages: int = 5) -> list[dict]:
        all_events = []
        for page in range(max_pages):
            events = await self.gamma.fetch_active_events(limit=100, offset=page * 100)
            if not events:
                break
            all_events.extend(events)
        return all_events

    def _parse_all_markets(self, events: list[dict]) -> list[dict]:
        all_markets = []
        for event in events:
            all_markets.extend(self.gamma.parse_markets(event))
        return all_markets

    async def sync_markets(self) -> int:
        events = await self._fetch_all_events()
        parsed = self._parse_all_markets(events)
        count = 0

        for data in parsed:
            existing = self.session.get(Market, data["id"])
            if existing:
                existing.last_price_yes = data["last_price_yes"]
                existing.last_price_no = data["last_price_no"]
                existing.volume_24h = data["volume_24h"]
                existing.liquidity = data["liquidity"]
                existing.active = data["active"]
                existing.updated_at = datetime.now(timezone.utc)
            else:
                end_date = None
                if data.get("end_date"):
                    try:
                        end_date = datetime.fromisoformat(data["end_date"].replace("Z", "+00:00"))
                    except ValueError:
                        pass

                market = Market(
                    id=data["id"],
                    condition_id=data["condition_id"],
                    token_id_yes=data["token_id_yes"],
                    token_id_no=data["token_id_no"],
                    question=data["question"],
                    slug=data.get("slug"),
                    category=data.get("category"),
                    end_date=end_date,
                    active=data["active"],
                    last_price_yes=data["last_price_yes"],
                    last_price_no=data["last_price_no"],
                    volume_24h=data["volume_24h"],
                    liquidity=data["liquidity"],
                )
                self.session.add(market)
            count += 1

        self.session.commit()
        return count
