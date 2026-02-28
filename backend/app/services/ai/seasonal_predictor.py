"""
SeasonalPredictor — Prophet-Based Seasonal Ticket Volume Forecasting

This module is an optional enhancement layer that activates ONLY when sufficient
historical data exists (MIN_DATA_POINTS daily observations for a ward+category pair).

When data is insufficient (early deployment), this module returns None silently
and the MemoryAgent falls back to its existing exact-match pattern detection.

Architecture:
  - One Prophet model per (ward_id, category) pair, trained on daily ticket counts
  - Models are cached in-memory after first training (lazy load)
  - Spike alert triggered when predicted next-30-day volume > 1.5x historical avg
  - Runs asynchronously in a background task — never blocks the main pipeline

Usage:
    predictor = get_seasonal_predictor()
    result = await predictor.predict_spike(ward_id=1, category="flooding")
    # Returns dict with alert info, or None if data insufficient
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 90   # Minimum daily observations to train Prophet (3 months)
SPIKE_THRESHOLD = 1.5  # Trigger alert if predicted > 1.5x historical average


class SeasonalPredictor:
    """
    Manages per-(ward, category) Prophet models for spike prediction.
    Models are lazily trained and cached in memory.
    """

    def __init__(self):
        self._models: Dict[str, Any] = {}          # key: "ward_category"
        self._last_trained: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    def _model_key(self, ward_id: int, category: str) -> str:
        return f"{ward_id}_{category.lower()}"

    async def _load_daily_counts(self, ward_id: int, category: str):
        """
        Fetches daily ticket counts for this (ward, category) pair from MongoDB.
        Returns a pandas DataFrame with columns ['ds', 'y'] as Prophet expects.
        """
        try:
            import pandas as pd
            from app.mongodb.models.ticket import TicketMongo

            # Fetch all tickets matching ward + category
            tickets = await TicketMongo.find(
                TicketMongo.ward_id == ward_id,
                TicketMongo.issue_category == category,
            ).to_list()

            if not tickets:
                return None

            # Build daily count series
            dates = [t.created_at.date() for t in tickets if hasattr(t, "created_at") and t.created_at]
            if len(dates) < MIN_DATA_POINTS:
                logger.debug(
                    "Prophet skipped for ward=%s cat=%s — only %d data points (need %d)",
                    ward_id, category, len(dates), MIN_DATA_POINTS,
                )
                return None

            df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": 1})
            df = df.groupby("ds").sum().reset_index()

            # Fill missing dates with 0 counts
            date_range = pd.date_range(df["ds"].min(), df["ds"].max(), freq="D")
            df = df.set_index("ds").reindex(date_range, fill_value=0).reset_index()
            df.columns = ["ds", "y"]

            return df

        except Exception as exc:
            logger.warning("SeasonalPredictor data load failed for ward=%s cat=%s: %s", ward_id, category, exc)
            return None

    async def _train(self, ward_id: int, category: str) -> bool:
        """Train (or retrain) a Prophet model. Returns True if successful."""
        try:
            from prophet import Prophet

            df = await self._load_daily_counts(ward_id, category)
            if df is None:
                return False

            model = Prophet(
                seasonality_mode="multiplicative",
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
                interval_width=0.80,
            )
            # Run Prophet fit in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, model.fit, df)

            key = self._model_key(ward_id, category)
            self._models[key] = {"model": model, "df_len": len(df)}
            self._last_trained[key] = datetime.utcnow()
            logger.info("ProphetModel trained for ward=%s cat=%s (%d days)", ward_id, category, len(df))
            return True

        except ImportError:
            logger.warning("Prophet not installed — seasonal spike prediction disabled.")
            return False
        except Exception as exc:
            logger.warning("Prophet training failed for ward=%s cat=%s: %s", ward_id, category, exc)
            return False

    async def predict_spike(
        self, ward_id: int, category: str, horizon_days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Predicts ticket volume for the next `horizon_days` days.
        Returns a spike alert dict if volume is predicted to exceed 1.5x normal, else None.

        Returns None silently if:
          - Insufficient historical data
          - Prophet not installed
          - Model training fails
        """
        key = self._model_key(ward_id, category)

        # Train or retrain (retrain weekly)
        should_train = (
            key not in self._models
            or (datetime.utcnow() - self._last_trained.get(key, datetime.min)).days >= 7
        )

        if should_train:
            async with self._lock:
                success = await self._train(ward_id, category)
                if not success:
                    return None

        entry = self._models.get(key)
        if not entry:
            return None

        try:
            import asyncio as _asyncio

            model = entry["model"]
            loop = _asyncio.get_event_loop()

            def _predict():
                future = model.make_future_dataframe(periods=horizon_days, freq="D")
                return model.predict(future)

            forecast = await loop.run_in_executor(None, _predict)

            # Next 30 days predicted volume
            predicted = forecast.tail(horizon_days)["yhat"].clip(lower=0).sum()

            # Historical daily average (exclude forecast horizon)
            historical_avg_daily = forecast.iloc[:-horizon_days]["yhat"].clip(lower=0).mean()
            historical_period_avg = historical_avg_daily * horizon_days

            if historical_period_avg <= 0:
                return None

            ratio = predicted / historical_period_avg

            if ratio >= SPIKE_THRESHOLD:
                return {
                    "alert": True,
                    "type": "prophet_spike",
                    "ward_id": ward_id,
                    "category": category,
                    "horizon_days": horizon_days,
                    "predicted_count": int(predicted),
                    "historical_avg_count": int(historical_period_avg),
                    "spike_ratio": round(ratio, 2),
                    "message": (
                        f"📈 Seasonal Spike Predicted: {int(predicted)} {category.replace('_', ' ')} "
                        f"reports expected in Ward {ward_id} over the next {horizon_days} days "
                        f"({int((ratio - 1) * 100)}% above historical average). "
                        f"Proactive inspection recommended."
                    ),
                }
            return None

        except Exception as exc:
            logger.warning("Prophet prediction failed for ward=%s cat=%s: %s", ward_id, category, exc)
            return None


# Module-level singleton
_predictor: Optional[SeasonalPredictor] = None


def get_seasonal_predictor() -> SeasonalPredictor:
    """Returns the singleton SeasonalPredictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = SeasonalPredictor()
    return _predictor
