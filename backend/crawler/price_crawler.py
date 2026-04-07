from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.crawler.clob_client import ClobClient
from backend.db.models import Market


class PriceCrawler:
    def __init__(self, session: Session, clob_client: ClobClient | None = None):
        self.session = session
        self.clob = clob_client or ClobClient()

    async def update_prices(self) -> int:
        markets = self.session.query(Market).filter(Market.active == True).all()
        if not markets:
            return 0

        token_ids = []
        token_to_market: dict[str, tuple[Market, str]] = {}
        for m in markets:
            token_ids.append(m.token_id_yes)
            token_ids.append(m.token_id_no)
            token_to_market[m.token_id_yes] = (m, "yes")
            token_to_market[m.token_id_no] = (m, "no")

        prices = await self.clob.get_prices_batch(token_ids)

        updated_markets = set()
        for token_id, price in prices.items():
            if token_id in token_to_market:
                market, side = token_to_market[token_id]
                if side == "yes":
                    market.last_price_yes = price
                else:
                    market.last_price_no = price
                market.updated_at = datetime.now(timezone.utc)
                updated_markets.add(market.id)

        self.session.commit()
        return len(updated_markets)
