"""
PriorityAgent — Hybrid Rule + ML Priority Scorer

Architecture:
  1. Rule engine  (deterministic, fast, always runs)
  2. ML model     (LightGBM classifier, batch retrain every 10 samples, activates after 50+)
  3. LLM override (only if rule and ML disagree by > 20 score points)

Final score = weighted average:
  - Rules  : 60% weight
  - ML     : 40% weight (when available)

The ML model persists in MongoDB (PriorityModelMongo) and self-improves via
batch retraining every time a ticket is closed (called from ticket_service.py).

New in v2:
  - LightGBM replaces SGDClassifier (non-linear, faster, SHAP-explainable)
  - Richer features: temporal (day_of_week, hour, monsoon flag), ward_id
  - explain_prediction() helper using SHAP TreeExplainer
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

SEVERITY_MAP = {
    "street_light_out": 15, "multiple_lights_out": 22,
    "electrical_spark_hazard": 30, "electrical_hazard": 30,
    "small_pothole": 12, "large_pothole": 20, "pothole": 16,
    "road_collapse": 28, "bridge_crack": 30,
    "low_pressure": 14, "no_water_supply": 22, "water": 16,
    "dirty_water": 25, "burst_pipe_flooding": 30,
    "drain_blocked": 18, "sewage_overflow": 26, "open_manhole": 30, "sewage": 20,
    "missed_collection_once": 10, "overflowing_bin": 16, "garbage": 14,
    "dead_animal_carcass": 22, "illegal_dumping_large": 20,
    "mosquito_breeding": 18, "stray_dog_bite": 28, "stray": 18,
    "disease_outbreak_concern": 30, "flood": 28, "flooding": 28,
    "fire": 30, "accident": 28, "collapse": 28,
    "default": 15,
}

SAFETY_KEYWORDS = [
    "accident", "danger", "hazard", "fire", "electric shock",
    "child fell", "injury", "death", "hospital", "emergency",
    "flood", "collapse", "snake", "rabies", "epidemic",
    "விபத்து", "ஆபத்து", "आग", "खतरा", "ప్రమాదం",
]


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
    """Pure rule-based scorer (0-100)."""
    base = SEVERITY_MAP.get(issue_category, SEVERITY_MAP["default"])
    safety_bonus = 5 if any(kw.lower() in description.lower() for kw in SAFETY_KEYWORDS) else 0
    severity = min(30, base + safety_bonus)

    location_scores = {
        "main_road": 10, "hospital_vicinity": 10, "school_vicinity": 9,
        "market": 8, "residential": 5, "internal_street": 3, "unknown": 4,
    }
    impact = min(15, report_count * 3) + location_scores.get(location_type, 4)

    if days_open <= 1: time_score = 0
    elif days_open <= 3: time_score = 5
    elif days_open <= 7: time_score = 10
    elif days_open <= 14: time_score = 15
    else: time_score = 20

    if hours_until_sla_breach <= 0: sla_score = 15
    elif hours_until_sla_breach <= 6: sla_score = 12
    elif hours_until_sla_breach <= 24: sla_score = 8
    elif hours_until_sla_breach <= 48: sla_score = 4
    else: sla_score = 0

    if social_media_mentions > 100: social_score = 10
    elif social_media_mentions > 50: social_score = 7
    elif social_media_mentions > 10: social_score = 4
    else: social_score = 0

    return min(100.0, severity + impact + time_score + sla_score + social_score)


def _score_to_label(score: float) -> str:
    if score >= 80: return "CRITICAL"
    elif score >= 60: return "HIGH"
    elif score >= 35: return "MEDIUM"
    return "LOW"


# ── Feature Engineering ───────────────────────────────────────────────────────

DEPT_IDS = ["D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08",
            "D09", "D10", "D11", "D12", "D13", "D14"]

FEATURE_NAMES = [
    # Core severity features
    "severity_base", "report_count", "days_open", "social_mentions",
    "sla_hours_remaining", "safety_flag",
    # Temporal features (NEW in v2)
    "month", "day_of_week", "hour_of_day", "is_weekend", "is_monsoon",
    # Ward-level feature (NEW in v2)
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
    safety_flag = 1.0 if any(kw.lower() in description.lower() for kw in SAFETY_KEYWORDS) else 0.0
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


# ── ML Model Manager (singleton) ─────────────────────────────────────────────

class _PriorityMLModel:
    """
    Singleton wrapper around LightGBM LGBMClassifier.
    LightGBM doesn't support partial_fit, so we accumulate all training
    samples in memory and fully retrain every 10 new samples.
    Thread-safe for async via asyncio.Lock on I/O-bound operations.
    """
    LABEL_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    LABEL_REVERSE = {v: k for k, v in LABEL_MAP.items()}
    MIN_SAMPLES_TO_USE = 50  # don't use ML predictions until we have enough data

    def __init__(self):
        self._clf = None
        self._sample_count = 0
        self._training_X: List[List[float]] = []
        self._training_y: List[int] = []
        self._lock = asyncio.Lock()

    def _build_fresh_model(self):
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
            doc = await PriorityModelMongo.find_one(PriorityModelMongo.is_active == True)
            if doc and doc.model_bytes:
                self._clf = joblib.load(io.BytesIO(doc.model_bytes))
                self._sample_count = doc.sample_count
                # Restore training buffer if persisted
                if hasattr(doc, "training_X") and doc.training_X:
                    self._training_X = doc.training_X
                    self._training_y = doc.training_y
                logger.info(
                    "Priority LightGBM model loaded from DB (samples=%d)", self._sample_count
                )
            else:
                logger.info(
                    "No trained priority model found. Will use rules only until %d samples.",
                    self.MIN_SAMPLES_TO_USE,
                )
        except Exception as exc:
            logger.warning("Could not load priority model from DB: %s", exc)

    def predict(self, features: List[float]) -> Optional[str]:
        """Returns label prediction if model is trained enough, else None."""
        if self._clf is None or self._sample_count < self.MIN_SAMPLES_TO_USE:
            return None
        try:
            X = np.array([features], dtype=float)
            label_int = self._clf.predict(X)[0]
            return self.LABEL_REVERSE.get(int(label_int), None)
        except Exception as exc:
            logger.warning("ML prediction failed: %s", exc)
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
        Online-style learning: accumulate a new labelled sample and retrain
        LightGBM every 10 new samples (full refit, not incremental).
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
                    X = np.array(self._training_X, dtype=float)
                    y = np.array(self._training_y, dtype=int)

                    clf = self._build_fresh_model()
                    clf.fit(X, y)
                    self._clf = clf

                    # Persist to MongoDB
                    model_buf = io.BytesIO()
                    joblib.dump(self._clf, model_buf)

                    await PriorityModelMongo.find(
                        PriorityModelMongo.is_active == True
                    ).update({"$set": {"is_active": False}})

                    new_doc = PriorityModelMongo(
                        model_bytes=model_buf.getvalue(),
                        scaler_bytes=b"",          # No scaler needed for LightGBM
                        feature_names=FEATURE_NAMES,
                        sample_count=self._sample_count,
                        is_active=True,
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
    """Call once at app startup."""
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
    - If they agree (or ML unavailable): use rule score + label
    - If they differ significantly (>20 points): blend (60% rules, 40% ML)
    """
    # 1. Rule score
    rule_score = _rule_score(
        issue_category, report_count, location_type, days_open,
        hours_until_sla_breach, social_media_mentions, description, month
    )
    rule_label = _score_to_label(rule_score)

    # 2. LightGBM prediction
    features = _build_feature_vector(
        issue_category, report_count, days_open, social_media_mentions,
        hours_until_sla_breach, month, description, dept_id,
        ward_id=ward_id, day_of_week=day_of_week, hour_of_day=hour_of_day,
    )
    ml_label = _ml_model.predict(features)

    if ml_label is None:
        # ML not ready — use rules only
        return round(rule_score, 2), rule_label, "rules"

    # Convert ML label to an approximate score for blending
    ml_score_map = {"LOW": 20, "MEDIUM": 50, "HIGH": 70, "CRITICAL": 90}
    ml_score = float(ml_score_map.get(ml_label, 50))

    if abs(rule_score - ml_score) <= 20:
        # Agreement — trust rules, which are more interpretable
        return round(rule_score, 2), rule_label, "hybrid"

    # Significant disagreement — blend (60% rules, 40% ML)
    blended_score = round(0.60 * rule_score + 0.40 * ml_score, 2)
    blended_label = _score_to_label(blended_score)
    return blended_score, blended_label, "hybrid"
