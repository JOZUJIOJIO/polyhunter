import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.db.models import Market, Signal
from backend.signals.base import SignalDetector

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert prediction market analyst. Given a prediction market question and its context, estimate the true probability that the event will resolve YES.

Respond ONLY with a JSON object in this exact format, no other text:
{"probability": 0.XX, "confidence": XX, "reasoning": "Your explanation here"}

- probability: your estimated probability (0.0 to 1.0) that the event resolves YES
- confidence: how confident you are in your estimate (0-100)
- reasoning: brief explanation of your reasoning (2-3 sentences max)"""

USER_PROMPT_TEMPLATE = """Market Question: {question}
Category: {category}
Current YES Price: ${yes_price:.2f}
Current NO Price: ${no_price:.2f}
24h Volume: ${volume:,.0f}
Liquidity: ${liquidity:,.0f}
End Date: {end_date}
Current Date: {today}

Estimate the true probability this resolves YES."""


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-4"


class AIPredictorDetector(SignalDetector):
    def __init__(self, session: Session, settings: Settings | None = None):
        super().__init__(session)
        self.settings = settings or Settings()
        self.api_key = self.settings.OPENROUTER_API_KEY
        self.model = self.settings.AI_MODEL

    def detect(self) -> list[Signal]:
        candidates = self._get_candidate_markets()
        if not candidates:
            return []

        signals = []
        for i, market in enumerate(candidates):
            if i > 0:
                time.sleep(self.settings.AI_REQUEST_DELAY_SECONDS)

            signal = self._analyze_market(market)
            if signal:
                signals.append(signal)

        return signals

    def _get_candidate_markets(self) -> list[Market]:
        now = datetime.now(timezone.utc)
        expiry_cutoff = now + timedelta(hours=self.settings.RISK_EXPIRY_BUFFER_HOURS)

        markets = (
            self.session.query(Market)
            .filter(
                Market.active == True,
                Market.last_price_yes.isnot(None),
                Market.last_price_no.isnot(None),
                Market.volume_24h >= self.settings.AI_MIN_VOLUME_24H,
                Market.liquidity >= self.settings.AI_MIN_LIQUIDITY,
            )
            .order_by(Market.volume_24h.desc())
            .limit(self.settings.AI_MAX_MARKETS_PER_RUN)
            .all()
        )

        # Filter out markets expiring too soon
        return [
            m for m in markets
            if not m.end_date or m.end_date.replace(tzinfo=timezone.utc) > expiry_cutoff
        ]

    def _analyze_market(self, market: Market) -> Signal | None:
        prompt = self._build_prompt(market)

        try:
            resp = httpx.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 256,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"AI API error for market {market.id}: {e}")
            return None

        ai_result = self._parse_response(text)
        if not ai_result:
            logger.warning(f"Failed to parse AI response for market {market.id}")
            return None

        return self._build_signal(market, ai_result)

    def _build_prompt(self, market: Market) -> str:
        end_date = "Not specified"
        if market.end_date:
            end_date = market.end_date.strftime("%Y-%m-%d")

        return USER_PROMPT_TEMPLATE.format(
            question=market.question,
            category=market.category or "General",
            yes_price=market.last_price_yes or 0,
            no_price=market.last_price_no or 0,
            volume=market.volume_24h or 0,
            liquidity=market.liquidity or 0,
            end_date=end_date,
            today=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )

    def _parse_response(self, text: str) -> dict | None:
        # Try to extract JSON from code fence or raw text
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            raw = json_match.group(1)
        else:
            # Try raw JSON
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            else:
                return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        # Validate required keys and types
        if not all(k in data for k in ("probability", "confidence", "reasoning")):
            return None

        prob = data["probability"]
        conf = data["confidence"]

        if not isinstance(prob, (int, float)) or not (0 <= prob <= 1):
            return None
        if not isinstance(conf, (int, float)) or not (0 <= conf <= 100):
            return None

        return {
            "probability": float(prob),
            "confidence": int(conf),
            "reasoning": str(data["reasoning"]),
        }

    def _build_signal(self, market: Market, ai_result: dict) -> Signal | None:
        ai_prob = ai_result["probability"]
        market_price = market.last_price_yes or 0

        edge = abs(ai_prob - market_price)
        edge_pct = edge * 100

        if edge_pct < self.settings.AI_EDGE_THRESHOLD_PCT:
            return None

        direction = "UNDERPRICED" if ai_prob > market_price else "OVERPRICED"

        return Signal(
            market_id=market.id,
            type="AI_PREDICTION",
            source_detail=json.dumps({
                "ai_probability": ai_result["probability"],
                "market_price": market_price,
                "edge_pct": round(edge_pct, 2),
                "direction": direction,
                "confidence": ai_result["confidence"],
                "reasoning": ai_result["reasoning"],
                "model": self.model,
            }),
            current_price=market_price,
            fair_value=round(ai_prob, 4),
            edge_pct=round(edge_pct, 2),
            confidence=min(ai_result["confidence"], 85),
            status="NEW",
        )
