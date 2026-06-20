"""Technical analysis indicators for trading strategies."""

from dataclasses import dataclass


@dataclass
class IndicatorResult:
    ema_fast: list[float]
    ema_slow: list[float]
    rsi: list[float]
    macd_line: list[float]
    macd_signal: list[float]
    macd_histogram: list[float]
    bb_upper: list[float]
    bb_middle: list[float]
    bb_lower: list[float]


def ema(prices: list[float], period: int) -> list[float]:
    """Exponential Moving Average."""
    if len(prices) < period:
        return [0.0] * len(prices)

    result = [0.0] * len(prices)
    multiplier = 2.0 / (period + 1)

    # SMA for first value
    result[period - 1] = sum(prices[:period]) / period

    for i in range(period, len(prices)):
        result[i] = (prices[i] - result[i - 1]) * multiplier + result[i - 1]

    return result


def sma(prices: list[float], period: int) -> list[float]:
    """Simple Moving Average."""
    if len(prices) < period:
        return [0.0] * len(prices)

    result = [0.0] * len(prices)
    for i in range(period - 1, len(prices)):
        result[i] = sum(prices[i - period + 1 : i + 1]) / period
    return result


def rsi(prices: list[float], period: int = 14) -> list[float]:
    """Relative Strength Index."""
    if len(prices) < period + 1:
        return [50.0] * len(prices)

    result = [50.0] * len(prices)
    gains = []
    losses = []

    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        gains.append(max(0, change))
        losses.append(max(0, -change))

    if len(gains) < period:
        return result

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(prices)):
        idx = i - 1  # gains/losses index
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


def macd(
    prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[list[float], list[float], list[float]]:
    """MACD (Moving Average Convergence Divergence)."""
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)

    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]

    return macd_line, signal_line, histogram


def bollinger_bands(
    prices: list[float], period: int = 20, std_dev: float = 2.0
) -> tuple[list[float], list[float], list[float]]:
    """Bollinger Bands."""
    middle = sma(prices, period)
    upper = [0.0] * len(prices)
    lower = [0.0] * len(prices)

    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        mean = middle[i]
        variance = sum((p - mean) ** 2 for p in window) / period
        std = variance ** 0.5
        upper[i] = mean + std_dev * std
        lower[i] = mean - std_dev * std

    return upper, middle, lower


def compute_all(
    prices: list[float],
    ema_fast_period: int = 9,
    ema_slow_period: int = 21,
    rsi_period: int = 14,
    bb_period: int = 20,
    bb_std: float = 2.0,
) -> IndicatorResult:
    """Compute all indicators at once."""
    ema_f = ema(prices, ema_fast_period)
    ema_s = ema(prices, ema_slow_period)
    rsi_vals = rsi(prices, rsi_period)
    macd_l, macd_sig, macd_hist = macd(prices)
    bb_up, bb_mid, bb_low = bollinger_bands(prices, bb_period, bb_std)

    return IndicatorResult(
        ema_fast=ema_f,
        ema_slow=ema_s,
        rsi=rsi_vals,
        macd_line=macd_l,
        macd_signal=macd_sig,
        macd_histogram=macd_hist,
        bb_upper=bb_up,
        bb_middle=bb_mid,
        bb_lower=bb_low,
    )
