"""Market Analyzer — 4-dimension weighted market regime assessment.

Dimensions
----------
1. **trend** (权重 0.30): MA5 vs MA20 vs MA60 多头/空头排列
2. **momentum** (权重 0.30): ROC(20), RSI(14)
3. **volatility** (权重 0.20): ATR(14) / 价格，判断市场状态
4. **volume** (权重 0.20): 成交量 vs 5日均量，判断量能

Composite score ranges from ``[-1, 1]`` where:
    - ``[-1.0, -0.5)`` → ``bearish``
    - ``[-0.5, -0.15)`` → ``cautious_bearish``
    - ``[-0.15, 0.15]`` → ``neutral``
    - ``(0.15, 0.5]`` → ``cautious_bullish``
    - ``(0.5, 1.0]`` → ``bullish``
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

_DIM_WEIGHTS: dict[str, float] = {
    "trend": 0.30,
    "momentum": 0.30,
    "volatility": 0.20,
    "volume": 0.20,
}

_VERDICT_MAP: list[tuple[float, float, str]] = [
    (-1.0, -0.5, "bearish"),
    (-0.5, -0.15, "cautious_bearish"),
    (-0.15, 0.15, "neutral"),
    (0.15, 0.5, "cautious_bullish"),
    (0.5, 1.0, "bullish"),
]

# Strategy recommendations per regime
_REGIME_STRATEGIES: dict[str, list[str]] = {
    "bullish": ["BullTrend", "ValueAverage"],
    "cautious_bullish": ["ValueAverage", "MovingAverageTrend"],
    "neutral": ["MeanReversion", "RSIRange"],
    "cautious_bearish": ["MeanReversion", "DefensiveMomentum"],
    "bearish": ["PutWrite", "DefensiveMomentum"],
}


class MarketAnalyzer:
    """4-dimension weighted market regime analyser.

    Parameters
    ----------
    store : AStockStore
        DuckDB-backed store from which kline data is queried.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, symbol: str, trade_date: str) -> dict[str, Any]:
        """Return 4-dimension analysis plus composite verdict.

        Parameters
        ----------
        symbol : str
            A-share symbol (e.g. ``"000300.SH"``).
        trade_date : str
            Date string in ``"YYYY-MM-DD"`` format.

        Returns
        -------
        dict
            ``symbol``, ``trade_date``, ``dimensions`` (per-dimension scores),
            ``composite_score``, ``market_verdict``, ``recommended_strategies``.
        """
        df = self._fetch_kline(symbol, trade_date)
        if df.empty:
            return self._empty_result(symbol, trade_date)

        dimensions: dict[str, dict[str, Any]] = {}
        dimensions["trend"] = self._analyze_trend(df)
        dimensions["momentum"] = self._analyze_momentum(df)
        dimensions["volatility"] = self._analyze_volatility(df)
        dimensions["volume"] = self._analyze_volume(df)

        composite = self._compute_composite(dimensions)
        verdict = self._classify_verdict(composite)
        strategies = _REGIME_STRATEGIES.get(verdict, ["MeanReversion"])

        return {
            "symbol": symbol,
            "trade_date": trade_date,
            "dimensions": dimensions,
            "composite_score": round(composite, 4),
            "market_verdict": verdict,
            "recommended_strategies": strategies,
        }

    def market_regime(self, symbol: str, lookback: int = 60) -> str:
        """Return overall market regime: ``"bull"`` / ``"oscillate"`` / ``"bear"``.

        Uses the composite score from the most recent date in the lookback
        window; if data is insufficient, returns ``"unknown"``.

        Parameters
        ----------
        symbol : str
            A-share symbol.
        lookback : int
            Number of trading days to look back (default ``60``).

        Returns
        -------
        str
            One of ``"bull"``, ``"oscillate"``, ``"bear"``, ``"unknown"``.
        """
        df = self._fetch_kline(symbol, lookback=lookback)
        if df.empty:
            return "unknown"

        recent = df.iloc[-1]
        trade_date = str(recent.name.date()) if hasattr(recent.name, "date") else str(recent.name)
        result = self.analyze(symbol, trade_date)
        composite = result.get("composite_score", 0.0)

        if composite > 0.3:
            return "bull"
        elif composite < -0.3:
            return "bear"
        elif composite != 0.0:
            return "oscillate"
        return "unknown"

    # ------------------------------------------------------------------
    # Dimension analysis
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze_trend(df: pd.DataFrame) -> dict[str, Any]:
        """Trend dimension: MA5 vs MA20 vs MA60 alignment.

        Score range ``[-1, 1]``:
            - MA5 > MA20 > MA60  (bullish) → ``+0.7`` to ``+1.0``
            - MA5 > MA20 < MA60  (mixed)   → ``0.0``
            - MA5 < MA20 > MA60  (mixed)   → ``0.0``
            - MA5 < MA20 < MA60  (bearish) → ``-0.7`` to ``-1.0``
        """
        close = df["close"]
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()

        last = df.index[-1]
        c5 = ma5.loc[last] if last in ma5.index else None
        c20 = ma20.loc[last] if last in ma20.index else None
        c60 = ma60.loc[last] if last in ma60.index else None

        if pd.isna(c5) or pd.isna(c20) or pd.isna(c60):
            return {"score": 0.0, "verdict": "neutral", "detail": "insufficient_data"}

        if c5 > c20 > c60:
            score = min(1.0, 0.7 + 0.3 * ((c5 - c60) / c60))
            return {"score": round(score, 4), "verdict": "bullish", "detail": f"MA5={c5:.2f}>MA20={c20:.2f}>MA60={c60:.2f}"}
        elif c5 < c20 < c60:
            score = max(-1.0, -0.7 - 0.3 * ((c60 - c5) / c60))
            return {"score": round(score, 4), "verdict": "bearish", "detail": f"MA5={c5:.2f}<MA20={c20:.2f}<MA60={c60:.2f}"}
        elif c5 > c20 and c20 <= c60:
            return {"score": 0.2, "verdict": "cautious_bullish", "detail": f"MA5={c5:.2f}>MA20={c20:.2f} but MA20≤MA60"}
        elif c5 <= c20 and c20 > c60:
            return {"score": -0.2, "verdict": "cautious_bearish", "detail": f"MA5≤MA20 but MA20={c20:.2f}>MA60={c60:.2f}"}
        return {"score": 0.0, "verdict": "neutral", "detail": f"MA5={c5:.2f} MA20={c20:.2f} MA60={c60:.2f}"}

    @staticmethod
    def _analyze_momentum(df: pd.DataFrame) -> dict[str, Any]:
        """Momentum dimension: ROC(20) + RSI(14).

        Score range ``[-1, 1]`` equally weighted from ROC and RSI.
        """
        close = df["close"]

        # ROC(20)
        roc = close.pct_change(20)
        last_roc = float(roc.iloc[-1]) if not roc.empty and not pd.isna(roc.iloc[-1]) else 0.0
        roc_score = max(-1.0, min(1.0, last_roc * 10.0))  # 10% move → ±1.0

        # RSI(14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100.0 - (100.0 / (1.0 + rs))
        last_rsi = float(rsi.iloc[-1]) if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50.0

        # Normalise RSI to [-1, 1]: 30 → -1, 50 → 0, 70 → +1
        if last_rsi >= 50:
            rsi_score = min(1.0, (last_rsi - 50.0) / 20.0)
        else:
            rsi_score = max(-1.0, (last_rsi - 50.0) / 20.0)

        combined = 0.5 * roc_score + 0.5 * rsi_score
        verdict = "bullish" if combined > 0.15 else "bearish" if combined < -0.15 else "neutral"

        return {
            "score": round(combined, 4),
            "verdict": verdict,
            "detail": f"RSI={last_rsi:.1f}, ROC={last_roc * 100:.2f}%",
        }

    @staticmethod
    def _analyze_volatility(df: pd.DataFrame) -> dict[str, Any]:
        """Volatility dimension: ATR(14) / price percentage.

        Score range ``[-1, 1]``:
            - Low volatility (ATR% < 1.5%) → ``+0.5`` (favourable)
            - Normal (1.5%–3%) → ``0.0``
            - High (> 3%) → ``-0.5`` to ``-1.0`` (risky)
        """
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr = pd.concat(
            [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(14).mean()
        last_atr = float(atr.iloc[-1]) if not atr.empty and not pd.isna(atr.iloc[-1]) else 0.0
        last_close = float(close.iloc[-1]) if not close.empty else 1.0
        atr_pct = last_atr / last_close if last_close > 0 else 0.0

        if atr_pct < 0.015:
            score = 0.5
            verdict = "low"
        elif atr_pct < 0.03:
            score = 0.0
            verdict = "normal"
        else:
            score = max(-1.0, -0.5 - 10.0 * (atr_pct - 0.03))
            verdict = "high"

        return {
            "score": round(score, 4),
            "verdict": verdict,
            "detail": f"ATR%={atr_pct * 100:.2f}%",
        }

    @staticmethod
    def _analyze_volume(df: pd.DataFrame) -> dict[str, Any]:
        """Volume dimension: current volume vs MA5.

        Score range ``[-1, 1]``:
            - Volume >> MA5 (active) → ``+0.6`` to ``+1.0``
            - Volume ~ MA5 (normal)  → ``0.0``
            - Volume << MA5 (weak)   → ``-0.5`` to ``-1.0``
        """
        volume = df["volume"]
        vol_ma5 = volume.rolling(5).mean()
        last_vol = float(volume.iloc[-1]) if not volume.empty else 0.0
        last_ma5 = float(vol_ma5.iloc[-1]) if not vol_ma5.empty and not pd.isna(vol_ma5.iloc[-1]) else last_vol

        ratio = last_vol / last_ma5 if last_ma5 > 0 else 1.0

        if ratio > 1.3:
            score = min(1.0, 0.6 + 0.4 * (ratio - 1.3) / 0.7)
            verdict = "active"
        elif ratio > 0.7:
            score = 0.0
            verdict = "normal"
        else:
            score = max(-1.0, -0.5 - 0.5 * (0.7 - ratio) / 0.7)
            verdict = "weak"

        return {
            "score": round(score, 4),
            "verdict": verdict,
            "detail": f"Vol/MA5={ratio:.2f}",
        }

    # ------------------------------------------------------------------
    # Composite
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_composite(
        dimensions: dict[str, dict[str, Any]]
    ) -> float:
        """Weighted average of all dimension scores."""
        total = 0.0
        for dim_name, dim_data in dimensions.items():
            weight = _DIM_WEIGHTS.get(dim_name, 0.0)
            total += weight * dim_data["score"]
        return total

    @staticmethod
    def _classify_verdict(composite: float) -> str:
        """Map composite score to a market verdict string."""
        for lo, hi, label in _VERDICT_MAP:
            if lo <= composite < hi:
                return label
        return "neutral"

    @staticmethod
    def _empty_result(symbol: str, trade_date: str) -> dict[str, Any]:
        """Return a neutral result when data is absent."""
        return {
            "symbol": symbol,
            "trade_date": trade_date,
            "dimensions": {
                k: {"score": 0.0, "verdict": "unknown", "detail": "no_data"}
                for k in _DIM_WEIGHTS
            },
            "composite_score": 0.0,
            "market_verdict": "neutral",
            "recommended_strategies": [],
        }

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _fetch_kline(
        self,
        symbol: str,
        trade_date: str | None = None,
        lookback: int = 80,
    ) -> pd.DataFrame:
        """Fetch kline data from the store.

        If *trade_date* is provided, fetches ``lookback`` days ending at
        that date.  Otherwise fetches the most recent ``lookback`` days.
        """
        if not hasattr(self._store, "query_kline"):
            return pd.DataFrame()

        try:
            df = self._store.query_kline(
                symbol=symbol, end=trade_date
            ) if trade_date else self._store.query_kline(symbol=symbol)

            if not isinstance(df, pd.DataFrame) or df.empty:
                return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

            df = df.copy()
            if "trade_date" in df.columns and "date" not in df.columns:
                df["date"] = pd.to_datetime(df["trade_date"])
            if "date" in df.columns:
                df = df.set_index("date").sort_index()

            for col in ("open", "high", "low", "close", "volume"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Trim to lookback window if trade_date was given
            if trade_date and lookback and len(df) > lookback:
                df = df.iloc[-lookback:]

            return df
        except Exception:
            return pd.DataFrame()
