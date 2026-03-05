"""
PriorityAgent — Hybrid Rule + ML Priority Scorer (v3)

Architecture:
  1. Rule engine  (deterministic, fast, always runs)
  2. ML model     (LightGBM classifier, batch retrains every 10 samples,
                   activates after 50+ training samples)
  3. On first startup, we warm-start with synthetic civic complaint data
     so the ML model is immediately usable even before real tickets accumulate.

Final score = weighted average:
  - Rules  : 60% weight
  - ML     : 40% weight (when available)

The ML model persists in MongoDB (PriorityModelMongo) and self-improves via
batch retraining every time a ticket is closed (called from ticket_service.py).

The warm-start synthetic dataset is only injected once (detected by DB check).

New in v3:
  - warm_start_with_synthetic_data() — 80 labelled synthetic samples
  - recalculate_priority() — useful when report_count / social_media_mentions
    change (e.g. after real-time scraper updates a ticket)
  - explain_priority() — human-readable explanation dict for the dashboard
  - Training buffer persisted to MongoDB (training_X / training_y fields)
"""
from __future__ import annotations

import io
import logging
import asyncio
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Rule Engine (pure function, no I/O) ──────────────────────────────────────

SEVERITY_MAP: Dict[str, int] = {
    # Streetlight
    "street_light_out": 15, "multiple_lights_out": 22,
    # Electrical
    "electrical_spark_hazard": 30, "electrical_hazard": 30,
    # Roads
    "small_pothole": 12, "large_pothole": 20, "pothole": 16,
    "road_collapse": 28, "bridge_crack": 30,
    # Water
    "low_pressure": 14, "no_water_supply": 22, "water": 16,
    "dirty_water": 25, "burst_pipe_flooding": 30,
    # Sewage
    "drain_blocked": 18, "sewage_overflow": 26, "open_manhole": 30, "sewage": 20,
    # Garbage
    "missed_collection_once": 10, "overflowing_bin": 16, "garbage": 14,
    "dead_animal_carcass": 22, "illegal_dumping_large": 20,
    # Health
    "mosquito_breeding": 18, "stray_dog_bite": 28, "stray": 18,
    "disease_outbreak_concern": 30,
    # Emergencies
    "flood": 28, "flooding": 28, "fire": 30, "accident": 28, "collapse": 28,
    # Default
    "default": 15,
}

SAFETY_KEYWORDS = [
    "accident", "danger", "hazard", "fire", "electric shock",
    "child fell", "injury", "death", "hospital", "emergency",
    "flood", "collapse", "snake", "rabies", "epidemic",
    # Tamil / Hindi / Telugu translations
    "விபத்து", "ஆபத்து", "आग", "खतरा", "ప్రమాదం",
]

LOCATION_SCORES: Dict[str, int] = {
    "main_road": 10, "hospital_vicinity": 10, "school_vicinity": 9,
    "market": 8, "residential": 5, "internal_street": 3, "unknown": 4,
}


def _rule_score(
    issue_category: str,
    report_count: int,
    location_type: str,
    days_open: int,
    hours_until_sla_breach: float,
    social_media_mentions: int,
    description: str,
    month: int = 6,
) -> float:
    """
    Pure rule-based scorer (0–100).

    Breakdown of maximum sub-scores:
      severity  : 30 pts  (issue type + safety keyword bonus)
      impact    : 25 pts  (report count up to 15 + location risk up to 10)
      time      : 20 pts  (age of issue)
      sla       : 15 pts  (SLA proximity)
      social    : 10 pts  (social media mentions)
    Total max  : 100 pts
    """
    # ── Severity (max 30) ────────────────────────────────────────────
    base = SEVERITY_MAP.get(issue_category, SEVERITY_MAP["default"])
    safety_bonus = 5 if any(
        kw.lower() in description.lower() for kw in SAFETY_KEYWORDS
    ) else 0
    severity = min(30, base + safety_bonus)

    # ── Impact (max 25) ──────────────────────────────────────────────
    report_contribution = min(15, report_count * 3)
    location_contribution = LOCATION_SCORES.get(location_type, 4)
    impact = report_contribution + location_contribution          # max = 15 + 10 = 25

    # ── Time (max 20) ────────────────────────────────────────────────
    if days_open <= 1:   time_score = 0
    elif days_open <= 3: time_score = 5
    elif days_open <= 7: time_score = 10
    elif days_open <= 14: time_score = 15
    else:                time_score = 20

    # ── SLA proximity (max 15) ───────────────────────────────────────
    if hours_until_sla_breach <= 0:    sla_score = 15
    elif hours_until_sla_breach <= 6:  sla_score = 12
    elif hours_until_sla_breach <= 24: sla_score = 8
    elif hours_until_sla_breach <= 48: sla_score = 4
    else:                               sla_score = 0

    # ── Social media (max 10) ────────────────────────────────────────
    if social_media_mentions > 100:    social_score = 10
    elif social_media_mentions > 50:   social_score = 7
    elif social_media_mentions > 10:   social_score = 4
    else:                               social_score = 0

    return float(min(100.0, severity + impact + time_score + sla_score + social_score))


def _score_to_label(score: float) -> str:
    """Map a numeric score (0–100) to a PriorityLabel string."""
    if score >= 80:   return "CRITICAL"
    elif score >= 60: return "HIGH"
    elif score >= 35: return "MEDIUM"
    return "LOW"


# ── Feature Engineering ───────────────────────────────────────────────────────

DEPT_IDS = [
    "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08",
    "D09", "D10", "D11", "D12", "D13", "D14",
]

FEATURE_NAMES = [
    # Core severity features
    "severity_base", "report_count", "days_open", "social_mentions",
    "sla_hours_remaining", "safety_flag",
    # Temporal features
    "month", "day_of_week", "hour_of_day", "is_weekend", "is_monsoon",
    # Ward-level feature
    "ward_id",
] + [f"dept_{d}" for d in DEPT_IDS]


def _build_feature_vector(
    issue_category: str,
    report_count: int,
    days_open: int,
    social_media_mentions: int,
    hours_until_sla_breach: float,
    month: int,
    description: str,
    dept_id: str,
    ward_id: int = 0,
    day_of_week: int = 0,   # 0=Monday … 6=Sunday
    hour_of_day: int = 12,
) -> List[float]:
    """Convert ticket attributes into a numeric feature vector for LightGBM."""
    severity_base = SEVERITY_MAP.get(issue_category, SEVERITY_MAP["default"])
    safety_flag = 1.0 if any(
        kw.lower() in description.lower() for kw in SAFETY_KEYWORDS
    ) else 0.0
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    is_monsoon = 1.0 if month in (6, 7, 8, 9) else 0.0
    dept_onehot = [1.0 if dept_id == d else 0.0 for d in DEPT_IDS]

    return [
        float(severity_base),
        float(min(report_count, 20)),
        float(min(days_open, 60)),
        float(min(social_media_mentions, 200)),
        float(max(0, hours_until_sla_breach)),
        safety_flag,
        float(month),
        float(day_of_week),
        float(hour_of_day),
        is_weekend,
        is_monsoon,
        float(ward_id),
    ] + dept_onehot


# ── Synthetic Warm-Start Dataset ──────────────────────────────────────────────

def _build_synthetic_training_data() -> Tuple[List[List[float]], List[int]]:
    """
    80 hand-crafted synthetic civic complaint samples covering all 4 priority labels.
    Used to warm-start the LightGBM model so it's usable from day 1.

    Label encoding: LOW=0, MEDIUM=1, HIGH=2, CRITICAL=3
    """
    LABEL = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    samples = []  # list of (kwargs, label)

    def s(cat, rc, do, sm, sla, mo, desc, dept, wid=1, dow=1, hod=10, lbl="MEDIUM"):
        samples.append((
            _build_feature_vector(cat, rc, do, sm, sla, mo, desc, dept, wid, dow, hod),
            LABEL[lbl],
        ))

    # ── CRITICAL issues ────────────────────────────────────────────────────────
    s("open_manhole", 15, 5, 120, -2, 7, "open manhole near school children playing", "D04", lbl="CRITICAL")
    s("flood", 20, 3, 200, -5, 8, "massive flooding accident emergency on main road", "D14", lbl="CRITICAL")
    s("electrical_hazard", 12, 8, 80, -1, 6, "live wire fell on road danger hazard", "D06", lbl="CRITICAL")
    s("burst_pipe_flooding", 18, 4, 150, -3, 7, "burst pipe flood near hospital emergency", "D03", lbl="CRITICAL")
    s("large_pothole", 10, 20, 90, -8, 5, "road collapse bridge crack emergency", "D01", lbl="CRITICAL")
    s("disease_outbreak_concern", 20, 6, 200, -10, 9, "dengue epidemic stray dog bite rabies", "D08", lbl="CRITICAL")
    s("fire", 5, 2, 180, 0, 11, "fire breaking out in market collapse hazard", "D09", lbl="CRITICAL")
    s("sewage_overflow", 16, 7, 100, -4, 8, "sewage overflow flooding street accident", "D04", lbl="CRITICAL")
    s("dead_animal_carcass", 8, 10, 60, -2, 7, "dead animals disease outbreak concern", "D08", lbl="CRITICAL")
    s("collapse", 10, 5, 200, -6, 6, "building collapse emergency accident area", "D09", lbl="CRITICAL")
    s("multiple_lights_out", 14, 12, 70, -3, 8, "multiple lights out near hospital dark hazard", "D06", lbl="CRITICAL")
    s("stray_dog_bite", 8, 3, 90, 0, 9, "stray dog bite injury hospital emergency", "D08", lbl="CRITICAL")
    s("flood", 20, 14, 150, -12, 7, "area flooded for 14 days no relief", "D14", lbl="CRITICAL")
    s("road_collapse", 12, 9, 110, -5, 6, "road collapsed near school dangerous", "D01", lbl="CRITICAL")
    s("burst_pipe_flooding", 15, 4, 80, -1, 8, "water pipe burst hospital vicinity flooding", "D03", lbl="CRITICAL")
    s("open_manhole", 18, 3, 60, 2, 7, "open manhole main road child fell in injury", "D04", lbl="CRITICAL")
    s("electrical_spark_hazard", 6, 5, 70, -2, 7, "electric shock accident near market bazaar", "D06", lbl="CRITICAL")
    s("flood", 20, 10, 200, -20, 9, "massive flood disaster relief needed urgently", "D14", lbl="CRITICAL")
    s("fire", 4, 1, 160, 0, 12, "factory fire emergency evacuation in progress", "D09", lbl="CRITICAL")
    s("sewage_overflow", 15, 6, 90, -3, 7, "sewage overflow floods road near school hospital", "D04", lbl="CRITICAL")

    # ── HIGH issues ────────────────────────────────────────────────────────────
    s("large_pothole", 8, 7, 60, 12, 6, "large pothole on main road vehicles damaged", "D01", lbl="HIGH")
    s("no_water_supply", 12, 5, 40, 20, 5, "5 days no water supply to entire colony", "D03", lbl="HIGH")
    s("overflowing_bin", 14, 6, 55, 8, 8, "garbage bins overflow market area smell", "D05", lbl="HIGH")
    s("drain_blocked", 10, 4, 45, 18, 7, "drain blocked streets flooded after rain", "D04", lbl="HIGH")
    s("multiple_lights_out", 9, 8, 30, 6, 9, "entire street dark for a week not safe", "D06", lbl="HIGH")
    s("illegal_dumping_large", 16, 3, 25, 30, 6, "large scale illegal dumping near park", "D02", lbl="HIGH")
    s("dirty_water", 13, 7, 50, 15, 8, "dirty brown water from taps bad smell", "D03", lbl="HIGH")
    s("mosquito_breeding", 10, 5, 40, 22, 9, "stagnant water mosquito breeding dengue risk", "D08", lbl="HIGH")
    s("road_collapse", 6, 3, 8, 48, 7, "large portion of road collapsed vehicles stuck", "D01", lbl="HIGH")
    s("pothole", 14, 6, 30, 10, 7, "dangerous pothole causing accidents on highway", "D01", lbl="HIGH")
    s("sewage", 11, 5, 12, 36, 8, "sewage backup in residential area strong smell", "D04", lbl="HIGH")
    s("no_water_supply", 8, 4, 25, 24, 6, "no water for 4 days in summer heat", "D03", lbl="HIGH")
    s("drain_blocked", 10, 5, 20, 48, 7, "blocked drain causing flooding near market", "D04", lbl="HIGH")
    s("electrical_hazard", 5, 2, 5, 20, 6, "exposed electrical wires near playground dangerous", "D06", lbl="HIGH")
    s("overflowing_bin", 12, 5, 40, 12, 6, "garbage pile growing near school health risk", "D05", lbl="HIGH")
    s("large_pothole", 7, 4, 35, 48, 8, "large pothole causing accidents near hospital", "D01", lbl="HIGH")
    s("disease_outbreak_concern", 5, 2, 15, 72, 8, "dogs biting residents in the area request action", "D08", lbl="HIGH")
    s("open_manhole", 3, 1, 20, 48, 6, "open manhole no cover near residential area", "D04", lbl="HIGH")
    s("burst_pipe_flooding", 4, 1, 2, 60, 7, "small pipe burst soaking road slippery", "D03", lbl="HIGH")
    s("flood", 8, 2, 55, 36, 9, "area frequently flooded during rain bad drainage", "D14", lbl="HIGH")

    # ── MEDIUM issues ──────────────────────────────────────────────────────────
    s("pothole", 3, 3, 5, 96, 5, "medium pothole near market slowing traffic", "D01", lbl="MEDIUM")
    s("garbage", 4, 2, 10, 120, 4, "garbage collection missed for 2 days", "D05", lbl="MEDIUM")
    s("street_light_out", 2, 4, 5, 80, 6, "street light not working near residential area", "D06", lbl="MEDIUM")
    s("drain_blocked", 3, 1, 3, 160, 7, "small drain blocked after rain", "D04", lbl="MEDIUM")
    s("water", 2, 3, 0, 100, 5, "low water pressure in the morning needs fix", "D03", lbl="MEDIUM")
    s("overflowing_bin", 3, 2, 5, 80, 8, "bin near park overflowing please clear it", "D05", lbl="MEDIUM")
    s("illegal_dumping_large", 2, 2, 4, 120, 4, "unauthorized dumping on empty plot residential area", "D02", lbl="MEDIUM")
    s("stray", 3, 1, 2, 150, 6, "stray dogs causing nuisance in street", "D08", lbl="MEDIUM")
    s("sewage", 2, 2, 4, 100, 5, "sewage smell in residential street", "D04", lbl="MEDIUM")
    s("pothole", 2, 3, 0, 90, 3, "small pothole at junction causing inconvenience", "D01", lbl="MEDIUM")
    s("mosquito_breeding", 2, 2, 5, 130, 6, "stagnant water nearby mosquito issue", "D08", lbl="MEDIUM")
    s("garbage", 3, 4, 8, 70, 7, "garbage dumped near market for 3 days", "D05", lbl="MEDIUM")
    s("low_pressure", 2, 2, 1, 120, 5, "water pressure very low in mornings", "D03", lbl="MEDIUM")
    s("street_light_out", 1, 5, 6, 60, 7, "4 streetlights not working in a row", "D06", lbl="MEDIUM")
    s("sewage", 3, 3, 5, 90, 9, "sewage odour blocking road walkway", "D04", lbl="MEDIUM")
    s("dead_animal_carcass", 1, 3, 5, 80, 6, "dead dog on roadside burning smell", "D08", lbl="MEDIUM")
    s("drain_blocked", 2, 2, 0, 140, 4, "drain partially clogged due to debris", "D04", lbl="MEDIUM")
    s("illegal_dumping_large", 3, 2, 3, 100, 6, "shop owners dumping waste outside shop", "D02", lbl="MEDIUM")
    s("overflowing_bin", 2, 4, 7, 60, 8, "overflowing bin outside school gate needs clearing", "D05", lbl="MEDIUM")
    s("water", 3, 2, 4, 90, 5, "water supply delayed by 2 hours daily", "D03", lbl="MEDIUM")

    # ── LOW issues ─────────────────────────────────────────────────────────────
    s("missed_collection_once", 1, 1, 0, 168, 3, "garbage collection missed yesterday", "D05", lbl="LOW")
    s("street_light_out", 1, 1, 0, 160, 5, "one streetlight flickering near park", "D06", lbl="LOW")
    s("small_pothole", 1, 0, 0, 168, 4, "small crack in footpath near home", "D01", lbl="LOW")
    s("low_pressure", 1, 0, 0, 168, 2, "water pressure slightly low in evening", "D03", lbl="LOW")
    s("garbage", 1, 1, 0, 150, 3, "few papers scattered near bus stop", "D05", lbl="LOW")
    s("street_light_out", 1, 2, 0, 140, 4, "street light at lane end not working", "D06", lbl="LOW")
    s("water", 1, 0, 0, 168, 6, "slight discolouration in water supply", "D03", lbl="LOW")
    s("missed_collection_once", 1, 0, 1, 168, 5, "bin not emptied in 2 days residential area", "D05", lbl="LOW")
    s("small_pothole", 1, 1, 0, 168, 4, "small pothole at end of lane", "D01", lbl="LOW")
    s("garbage", 1, 0, 0, 168, 3, "minor littering near park no smell", "D05", lbl="LOW")
    s("missed_collection_once", 1, 1, 0, 168, 6, "garbage not collected on monday as usual", "D05", lbl="LOW")
    s("street_light_out", 1, 1, 0, 168, 7, "bulb blown in lane streetlight", "D06", lbl="LOW")
    s("small_pothole", 1, 0, 0, 168, 3, "tiny hollow near footpath joint", "D01", lbl="LOW")
    s("low_pressure", 1, 0, 0, 168, 1, "pressure dips at midnight no issue mostly", "D03", lbl="LOW")
    s("missed_collection_once", 1, 0, 0, 168, 2, "collection truck missed our area once", "D05", lbl="LOW")
    s("street_light_out", 1, 1, 0, 168, 9, "light pole near house door needs bulb", "D06", lbl="LOW")
    s("small_pothole", 1, 0, 0, 168, 4, "small dip near road corner", "D01", lbl="LOW")
    s("garbage", 1, 0, 0, 168, 5, "paper cups around temple premises", "D05", lbl="LOW")
    s("water", 1, 0, 0, 168, 7, "slight smell in water no major issue", "D03", lbl="LOW")
    s("missed_collection_once", 1, 0, 0, 168, 10, "garbage bin near apartment not picked up", "D05", lbl="LOW")

    X = [row[0] for row in samples]
    y = [row[1] for row in samples]
    return X, y


# ── ML Model Manager (singleton) ─────────────────────────────────────────────

class _PriorityMLModel:
    """
    Singleton wrapper around LightGBM LGBMClassifier.

    LightGBM doesn't support partial_fit, so we accumulate all training
    samples in memory and fully retrain every 10 new real samples.
    Thread-safe for async via asyncio.Lock on I/O-bound operations.

    Warm-start: if the DB has no saved model, we train on 80 synthetic
    samples so predictions are available immediately on a fresh deployment.
    """
    LABEL_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    LABEL_REVERSE = {v: k for k, v in LABEL_MAP.items()}
    MIN_SAMPLES_TO_USE = 50   # don't use ML predictions until we have enough data

    def __init__(self):
        self._clf = None
        self._sample_count = 0
        self._training_X: List[List[float]] = []
        self._training_y: List[int] = []
        self._lock = asyncio.Lock()

    def _build_fresh_model(self):
        """Create a new LightGBM classifier (falls back to SGD if lgbm unavailable)."""
        try:
            from lightgbm import LGBMClassifier
            return LGBMClassifier(
                objective="multiclass",
                num_class=4,
                learning_rate=0.05,
                num_leaves=31,
                n_estimators=100,
                feature_fraction=0.8,
                bagging_fraction=0.8,
                bagging_freq=5,
                random_state=42,
                class_weight="balanced",
                verbose=-1,
            )
        except ImportError:
            logger.warning("LightGBM not installed. Falling back to SGDClassifier.")
            from sklearn.linear_model import SGDClassifier
            return SGDClassifier(
                loss="modified_huber",
                max_iter=1000,
                random_state=42,
                class_weight="balanced",
            )

    async def load_from_db(self):
        """Load the most recent model + training buffer from MongoDB on startup."""
        try:
            import joblib
            from app.mongodb.models.priority_model import PriorityModelMongo
            doc = await PriorityModelMongo.find_one(
                PriorityModelMongo.is_active == True
            )
            if doc and doc.model_bytes:
                self._clf = joblib.load(io.BytesIO(doc.model_bytes))
                self._sample_count = doc.sample_count
                # Restore training buffer if persisted
                if doc.training_X:
                    self._training_X = doc.training_X
                    self._training_y = doc.training_y
                logger.info(
                    "Priority LightGBM model loaded from DB (samples=%d)",
                    self._sample_count,
                )
            else:
                logger.info(
                    "No trained priority model found. Running warm-start with synthetic data."
                )
                await self._warm_start()
        except Exception as exc:
            logger.warning("Could not load priority model from DB: %s", exc)
            # Best-effort warm start even if DB is unreachable at load time
            try:
                await self._warm_start()
            except Exception:
                pass

    @staticmethod
    def _to_df(X_rows: List[List[float]]):
        """Convert list-of-lists to a pandas DataFrame with named columns.
        Falls back to numpy array if pandas is not available."""
        try:
            import pandas as pd
            return pd.DataFrame(X_rows, columns=FEATURE_NAMES)
        except ImportError:
            return np.array(X_rows, dtype=float)

    async def _warm_start(self):
        """
        Train on 80 synthetic civic complaint samples so the ML model is
        usable from day 1 without waiting for real ticket accumulation.
        The DB persistence is skipped here (happens on next real-data retrain).
        """
        X, y = _build_synthetic_training_data()
        self._training_X = list(X)
        self._training_y = list(y)

        clf = self._build_fresh_model()
        X_df = self._to_df(X)
        y_np = np.array(y, dtype=int)
        clf.fit(X_df, y_np)
        self._clf = clf
        self._sample_count = len(X)  # 80 synthetic samples
        logger.info(
            "Priority model warm-started with %d synthetic samples (ML active).",
            self._sample_count,
        )

    def predict(self, features: List[float]) -> Optional[str]:
        """Returns label prediction if model is trained enough, else None."""
        if self._clf is None or self._sample_count < self.MIN_SAMPLES_TO_USE:
            return None
        try:
            X = self._to_df([features])
            label_int = self._clf.predict(X)[0]
            return self.LABEL_REVERSE.get(int(label_int), None)
        except Exception as exc:
            logger.warning("ML prediction failed: %s", exc)
            return None

    def predict_proba(self, features: List[float]) -> Optional[Dict[str, float]]:
        """Returns {label: probability} dict if available."""
        if self._clf is None or self._sample_count < self.MIN_SAMPLES_TO_USE:
            return None
        try:
            X = self._to_df([features])
            proba = self._clf.predict_proba(X)[0]
            return {self.LABEL_REVERSE[i]: float(p) for i, p in enumerate(proba)}
        except Exception as exc:
            logger.warning("ML predict_proba failed: %s", exc)
            return None

    def explain_prediction(self, features: List[float]) -> Optional[Dict[str, float]]:
        """
        Returns a dict of {feature_name: shap_value} for the predicted class.
        Returns None if shap is not installed or model not ready.
        """
        if self._clf is None or self._sample_count < self.MIN_SAMPLES_TO_USE:
            return None
        try:
            import shap
            X = np.array([features], dtype=float)
            explainer = shap.TreeExplainer(self._clf)
            shap_values = explainer.shap_values(X)
            # shap_values shape: (num_classes, n_samples, n_features)
            predicted_class = int(self._clf.predict(X)[0])
            class_shap = shap_values[predicted_class][0]
            return {name: float(val) for name, val in zip(FEATURE_NAMES, class_shap)}
        except Exception as exc:
            logger.debug("SHAP explanation skipped: %s", exc)
            return None

    async def add_training_sample(self, features: List[float], true_label: str):
        """
        Accumulate a new labelled sample and retrain LightGBM every 10 new
        real samples (full refit, not incremental).
        Called when a ticket is closed (true_label = the final confirmed priority).
        """
        async with self._lock:
            try:
                import joblib
                from app.mongodb.models.priority_model import PriorityModelMongo

                label_int = self.LABEL_MAP.get(true_label, 1)
                self._training_X.append(features)
                self._training_y.append(label_int)
                self._sample_count += 1

                # Retrain every 10 new samples
                if self._sample_count % 10 == 0:
                    X_df = self._to_df(self._training_X)
                    y = np.array(self._training_y, dtype=int)

                    clf = self._build_fresh_model()
                    clf.fit(X_df, y)
                    self._clf = clf

                    # Persist to MongoDB
                    model_buf = io.BytesIO()
                    joblib.dump(self._clf, model_buf)

                    await PriorityModelMongo.find(
                        PriorityModelMongo.is_active == True
                    ).update({"$set": {"is_active": False}})

                    new_doc = PriorityModelMongo(
                        model_bytes=model_buf.getvalue(),
                        scaler_bytes=b"",
                        feature_names=FEATURE_NAMES,
                        sample_count=self._sample_count,
                        is_active=True,
                        training_X=self._training_X,
                        training_y=self._training_y,
                    )
                    await new_doc.insert()
                    logger.info(
                        "Priority LightGBM model retrained and saved (samples=%d)",
                        self._sample_count,
                    )
            except Exception as exc:
                logger.error("ML training sample failed: %s", exc)


# Module-level singleton
_ml_model = _PriorityMLModel()


async def load_priority_model():
    """Call once at app startup (loads model from DB or warm-starts with synthetic data)."""
    await _ml_model.load_from_db()


async def train_on_closed_ticket(
    issue_category: str,
    report_count: int,
    days_open: int,
    social_media_mentions: int,
    hours_until_sla_breach: float,
    month: int,
    description: str,
    dept_id: str,
    confirmed_priority_label: str,
    ward_id: int = 0,
    day_of_week: int = 0,
    hour_of_day: int = 12,
):
    """
    Called when a ticket is closed. Trains the LightGBM model with verified data.
    The confirmed_priority_label is the ground truth (human-confirmed outcome).
    """
    features = _build_feature_vector(
        issue_category, report_count, days_open, social_media_mentions,
        hours_until_sla_breach, month, description, dept_id,
        ward_id=ward_id, day_of_week=day_of_week, hour_of_day=hour_of_day,
    )
    await _ml_model.add_training_sample(features, confirmed_priority_label)


# ── Main Priority Function ────────────────────────────────────────────────────

async def calculate_priority(
    issue_category: str,
    description: str,
    dept_id: str,
    report_count: int = 1,
    location_type: str = "unknown",
    days_open: int = 0,
    hours_until_sla_breach: float = 168.0,
    social_media_mentions: int = 0,
    month: int = 6,
    ward_id: int = 0,
    day_of_week: int = 0,
    hour_of_day: int = 12,
) -> Tuple[float, str, str]:
    """
    Returns (score: float, label: str, source: str)
    source is one of: "rules", "ml", "hybrid"

    Hybrid logic:
    - Build rule score (always)
    - If LightGBM is available, build ML prediction
    - If they agree (within 20 score pts) OR ML unavailable: use rule score
    - If they differ significantly (>20 pts): blend (60% rules, 40% ML)
    """
    # 1. Rule score (always computed)
    rule_score = _rule_score(
        issue_category, report_count, location_type, days_open,
        hours_until_sla_breach, social_media_mentions, description, month
    )
    rule_label = _score_to_label(rule_score)

    # 2. LightGBM feature vector and prediction
    features = _build_feature_vector(
        issue_category, report_count, days_open, social_media_mentions,
        hours_until_sla_breach, month, description, dept_id,
        ward_id=ward_id, day_of_week=day_of_week, hour_of_day=hour_of_day,
    )
    ml_label = _ml_model.predict(features)

    if ml_label is None:
        # ML not ready (or warm-start not done) — use rules only
        return round(rule_score, 2), rule_label, "rules"

    # Convert ML label to an approximate midpoint score for blending
    ml_score_map = {"LOW": 20.0, "MEDIUM": 50.0, "HIGH": 70.0, "CRITICAL": 90.0}
    ml_score = ml_score_map.get(ml_label, 50.0)

    if abs(rule_score - ml_score) <= 20:
        # Agreement — trust rules (more interpretable)
        return round(rule_score, 2), rule_label, "hybrid"

    # Significant disagreement — blend (60% rules, 40% ML)
    blended_score = round(0.60 * rule_score + 0.40 * ml_score, 2)
    blended_label = _score_to_label(blended_score)
    return blended_score, blended_label, "hybrid"


async def recalculate_priority(
    ticket_id: str,
    new_report_count: Optional[int] = None,
    new_social_mentions: Optional[int] = None,
) -> Optional[Tuple[float, str, str]]:
    """
    Re-score an existing ticket in-DB when its report_count or social_media_mentions
    are updated by the real-time data scraper. Saves the updated score to MongoDB.

    Returns (new_score, new_label, source) or None if ticket not found.
    """
    try:
        from beanie import PydanticObjectId
        from app.mongodb.models.ticket import TicketMongo
        from datetime import datetime

        # Find by ticket_code string (not ObjectId)
        ticket = await TicketMongo.find_one(TicketMongo.ticket_code == ticket_id)
        if not ticket:
            logger.warning("recalculate_priority: ticket %s not found", ticket_id)
            return None

        # Use incoming overrides or existing values
        rc = new_report_count if new_report_count is not None else ticket.report_count
        sm = new_social_mentions if new_social_mentions is not None else ticket.social_media_mentions

        # Calculate SLA proximity
        hours_remaining = (
            (ticket.sla_deadline - datetime.utcnow()).total_seconds() / 3600
            if ticket.sla_deadline else 168.0
        )
        days_open = (datetime.utcnow() - ticket.created_at).days
        now = datetime.utcnow()

        new_score, new_label, source = await calculate_priority(
            issue_category=ticket.issue_category or "default",
            description=ticket.description,
            dept_id=ticket.dept_id,
            report_count=rc,
            location_type="unknown",
            days_open=days_open,
            hours_until_sla_breach=hours_remaining,
            social_media_mentions=sm,
            month=now.month,
            ward_id=ticket.ward_id or 0,
            day_of_week=now.weekday(),
            hour_of_day=now.hour,
        )

        # Persist updates
        from app.enums import PriorityLabel
        ticket.priority_score = new_score
        ticket.priority_label = PriorityLabel(new_label)
        ticket.priority_source = source
        if new_report_count is not None:
            ticket.report_count = new_report_count
        if new_social_mentions is not None:
            ticket.social_media_mentions = new_social_mentions
        await ticket.save()

        logger.info(
            "recalculate_priority: %s → score=%.1f label=%s source=%s",
            ticket_id, new_score, new_label, source,
        )
        return new_score, new_label, source

    except Exception as exc:
        logger.error("recalculate_priority failed for %s: %s", ticket_id, exc)
        return None


def explain_priority(
    issue_category: str,
    description: str,
    dept_id: str,
    report_count: int = 1,
    location_type: str = "unknown",
    days_open: int = 0,
    hours_until_sla_breach: float = 168.0,
    social_media_mentions: int = 0,
    month: int = 6,
    ward_id: int = 0,
    day_of_week: int = 0,
    hour_of_day: int = 12,
) -> Dict[str, Any]:
    """
    Returns a human-readable explanation of the priority score breakdown.
    This is a synchronous function suitable for API response enrichment.

    Useful for the councillor dashboard "Why is this CRITICAL?" panel.
    """
    rule_score = _rule_score(
        issue_category, report_count, location_type, days_open,
        hours_until_sla_breach, social_media_mentions, description, month
    )
    safety_flag = any(kw.lower() in description.lower() for kw in SAFETY_KEYWORDS)
    severity_base = SEVERITY_MAP.get(issue_category, SEVERITY_MAP["default"])
    report_contribution = min(15, report_count * 3)
    location_contribution = LOCATION_SCORES.get(location_type, 4)

    # Time score
    if days_open <= 1:    time_score = 0
    elif days_open <= 3:  time_score = 5
    elif days_open <= 7:  time_score = 10
    elif days_open <= 14: time_score = 15
    else:                 time_score = 20

    # SLA score
    if hours_until_sla_breach <= 0:    sla_score = 15
    elif hours_until_sla_breach <= 6:  sla_score = 12
    elif hours_until_sla_breach <= 24: sla_score = 8
    elif hours_until_sla_breach <= 48: sla_score = 4
    else:                               sla_score = 0

    # Social score
    if social_media_mentions > 100:    social_score = 10
    elif social_media_mentions > 50:   social_score = 7
    elif social_media_mentions > 10:   social_score = 4
    else:                               social_score = 0

    features = _build_feature_vector(
        issue_category, report_count, days_open, social_media_mentions,
        hours_until_sla_breach, month, description, dept_id,
        ward_id=ward_id, day_of_week=day_of_week, hour_of_day=hour_of_day,
    )
    shap_explanation = _ml_model.explain_prediction(features)
    ml_probas = _ml_model.predict_proba(features)

    return {
        "rule_score": round(rule_score, 2),
        "rule_label": _score_to_label(rule_score),
        "breakdown": {
            "severity":  {"score": min(30, severity_base + (5 if safety_flag else 0)),
                          "max": 30,
                          "note": f"Issue type '{issue_category}' base={severity_base}"
                                  + (" + safety keyword detected!" if safety_flag else "")},
            "impact":    {"score": report_contribution + location_contribution,
                          "max": 25,
                          "note": f"{report_count} report(s) (+{report_contribution}) "
                                  f"at '{location_type}' (+{location_contribution})"},
            "age":       {"score": time_score,
                          "max": 20,
                          "note": f"Open for {days_open} day(s)"},
            "sla":       {"score": sla_score,
                          "max": 15,
                          "note": f"{hours_until_sla_breach:.1f}h until SLA breach"},
            "social":    {"score": social_score,
                          "max": 10,
                          "note": f"{social_media_mentions} social mention(s)"},
        },
        "ml_probabilities": ml_probas,
        "shap_feature_importance": shap_explanation,
        "ml_model_active": _ml_model._clf is not None and _ml_model._sample_count >= _ml_model.MIN_SAMPLES_TO_USE,
        "ml_sample_count": _ml_model._sample_count,
    }
