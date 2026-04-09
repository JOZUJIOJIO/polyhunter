"""BTC AI 预测器测试"""

from unittest.mock import patch, MagicMock

from backend.btc.predictor import BTCPredictor


class TestBTCPredictorParse:
    def setup_method(self):
        self.predictor = BTCPredictor.__new__(BTCPredictor)

    def test_valid_json(self):
        text = '{"prediction": "YES", "probability": 0.65, "confidence": 72, "reasoning": "BTC shows strength"}'
        result = self.predictor._parse(text)
        assert result is not None
        assert result["prediction"] == "YES"
        assert result["probability"] == 0.65
        assert result["confidence"] == 72

    def test_confidence_capped_at_85(self):
        text = '{"prediction": "NO", "probability": 0.8, "confidence": 95, "reasoning": "Very confident"}'
        result = self.predictor._parse(text)
        assert result["confidence"] == 85

    def test_json_embedded_in_text(self):
        text = 'Here is my analysis:\n{"prediction": "YES", "probability": 0.55, "confidence": 60, "reasoning": "Moderate"}\nEnd.'
        result = self.predictor._parse(text)
        assert result is not None
        assert result["prediction"] == "YES"

    def test_invalid_probability(self):
        text = '{"prediction": "YES", "probability": 1.5, "confidence": 60, "reasoning": "Bad"}'
        result = self.predictor._parse(text)
        assert result is None

    def test_invalid_confidence(self):
        text = '{"prediction": "YES", "probability": 0.5, "confidence": -10, "reasoning": "Bad"}'
        result = self.predictor._parse(text)
        assert result is None

    def test_missing_field(self):
        text = '{"prediction": "YES", "probability": 0.5}'
        result = self.predictor._parse(text)
        assert result is None

    def test_no_json(self):
        result = self.predictor._parse("No JSON here")
        assert result is None

    def test_prediction_normalized_to_upper(self):
        text = '{"prediction": "yes", "probability": 0.5, "confidence": 50, "reasoning": "test"}'
        result = self.predictor._parse(text)
        assert result["prediction"] == "YES"


class TestBTCPredictorPredict:
    @patch("backend.btc.predictor.httpx.post")
    def test_successful_prediction(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"prediction": "YES", "probability": 0.65, "confidence": 70, "reasoning": "Bullish"}'}}]
        }
        mock_post.return_value = mock_resp

        predictor = BTCPredictor.__new__(BTCPredictor)
        predictor.settings = MagicMock()
        predictor.settings.OPENROUTER_API_KEY = "test-key"
        predictor.settings.AI_MODEL = "test-model"

        indicators = {
            "current_price": 80000,
            "high_24h": 81000,
            "low_24h": 79000,
            "sma_7h": 80100,
            "sma_24h": 79800,
            "rsi_14": 55,
            "rsi_signal": "中性",
            "macd": 50,
            "macd_signal": "看涨",
            "bb_upper": 81500,
            "bb_lower": 78500,
            "volatility_24h": 1.5,
            "trend_24h_pct": 0.8,
            "above_sma_24": True,
        }

        result = predictor.predict(indicators, 81000, "突破", 0.45, 0.55)
        assert result is not None
        assert result["prediction"] == "YES"

    @patch("backend.btc.predictor.httpx.post")
    def test_api_failure_returns_none(self, mock_post):
        mock_post.side_effect = Exception("Network error")

        predictor = BTCPredictor.__new__(BTCPredictor)
        predictor.settings = MagicMock()
        predictor.settings.OPENROUTER_API_KEY = "test-key"
        predictor.settings.AI_MODEL = "test-model"

        indicators = {
            "current_price": 80000, "high_24h": 81000, "low_24h": 79000,
            "sma_7h": 80000, "sma_24h": 80000, "rsi_14": 50, "rsi_signal": "中性",
            "macd": 0, "macd_signal": "看跌", "bb_upper": 81000, "bb_lower": 79000,
            "volatility_24h": 1.0, "trend_24h_pct": 0, "above_sma_24": False,
        }
        result = predictor.predict(indicators, 80000, "突破", 0.5, 0.5)
        assert result is None
