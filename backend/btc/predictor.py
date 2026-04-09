"""
BTC 日级 AI 预测器
用 Claude 分析技术指标 + 市场数据，预测 BTC 能否突破特定关口
"""

import json
import logging
import re

import httpx

from backend.config import Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的加密货币技术分析师。根据 BTC 当前技术指标和市场数据，判断 BTC 在今天收盘时能否突破指定的价格关口。

你必须只返回一个 JSON 对象，不要有其他文字：
{"prediction": "YES或NO", "probability": 0.XX, "confidence": XX, "reasoning": "你的分析"}

- prediction: "YES"表示你认为能突破, "NO"表示不能
- probability: 突破该关口的概率 (0.0-1.0)
- confidence: 你对这个判断的信心 (0-100)
- reasoning: 简短分析 (2-3句话)"""

USER_PROMPT_TEMPLATE = """BTC 当前技术指标：
- 当前价格: ${current_price:,.0f}
- 24h 最高: ${high_24h:,.0f}
- 24h 最低: ${low_24h:,.0f}
- 7h 均线: ${sma_7h:,.0f}
- 24h 均线: ${sma_24h:,.0f}
- RSI(14): {rsi_14} ({rsi_signal})
- MACD: {macd} ({macd_signal})
- 布林带上轨: ${bb_upper:,.0f}
- 布林带下轨: ${bb_lower:,.0f}
- 24h 波动率: {volatility_24h}%
- 24h 趋势: {trend_24h_pct}%
- 是否在24h均线上方: {above_sma_24}

问题：BTC 今天收盘时能否 {direction} ${threshold:,}？
当前市场价: YES=${market_yes:.2f} NO=${market_no:.2f}"""


class BTCPredictor:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def predict(
        self,
        indicators: dict,
        threshold: int,
        direction: str,
        market_yes: float,
        market_no: float,
    ) -> dict | None:
        """
        预测 BTC 能否突破指定关口

        Args:
            indicators: compute_indicators() 的输出
            threshold: 价格关口 (如 78000)
            direction: "突破" 或 "跌破"
            market_yes: Polymarket YES 当前价格
            market_no: Polymarket NO 当前价格

        Returns:
            {"prediction": "YES/NO", "probability": float, "confidence": int, "reasoning": str}
        """
        prompt = USER_PROMPT_TEMPLATE.format(
            **indicators,
            threshold=threshold,
            direction=direction,
            market_yes=market_yes,
            market_no=market_no,
        )

        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.AI_MODEL,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"AI API error: {e}")
            return None

        return self._parse(text)

    def _parse(self, text: str) -> dict | None:
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not json_match:
            return None
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return None

        required = ("prediction", "probability", "confidence", "reasoning")
        if not all(k in data for k in required):
            return None

        prob = data["probability"]
        conf = data["confidence"]
        if not isinstance(prob, (int, float)) or not (0 <= prob <= 1):
            return None
        if not isinstance(conf, (int, float)) or not (0 <= conf <= 100):
            return None

        return {
            "prediction": str(data["prediction"]).upper(),
            "probability": float(prob),
            "confidence": min(int(conf), 85),
            "reasoning": str(data["reasoning"]),
        }
