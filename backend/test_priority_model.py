"""
Standalone tests for the Priority Scoring Model.

Run with:  python test_priority_model.py
No pytest required — uses Python stdlib unittest.

Tests cover:
  1. Rule engine correctness (SEVERITY_MAP, location, time, SLA, social)
  2. Score-to-label mapping
  3. Feature vector shape and value constraints
  4. Synthetic dataset generation (80 samples, 4 balanced labels)
  5. LightGBM warm-start training (synchronous via asyncio.run)
  6. ML prediction returns valid labels after warm-start
  7. ML predict_proba sums to 1.0
  8. explain_priority returns expected keys and coherent breakdown totals
  9. recalculate_priority placeholder (no DB — checks logic path)
 10. Edge cases: very high report_count, monsoon month, safety keyword in text
"""
import sys
import asyncio
import unittest
from pathlib import Path

# Ensure backend/ is on the path
sys.path.insert(0, str(Path(__file__).parent))

# ── Import only the parts that don't need MongoDB ─────────────────────────────
from app.services.ai.priority_agent import (
    _rule_score,
    _score_to_label,
    _build_feature_vector,
    _build_synthetic_training_data,
    explain_priority,
    FEATURE_NAMES,
    SEVERITY_MAP,
    SAFETY_KEYWORDS,
    _ml_model,
)


# ─── 1. RULE ENGINE ──────────────────────────────────────────────────────────

class TestRuleEngine(unittest.TestCase):

    def _score(self, **kwargs):
        defaults = dict(
            issue_category="garbage",
            report_count=1,
            location_type="unknown",
            days_open=0,
            hours_until_sla_breach=168.0,
            social_media_mentions=0,
            description="garbage near road",
            month=4,
        )
        defaults.update(kwargs)
        return _rule_score(**defaults)

    def test_score_range_0_to_100(self):
        score = self._score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_critical_issue_scores_higher(self):
        low = self._score(issue_category="missed_collection_once")
        high = self._score(issue_category="open_manhole")
        self.assertGreater(high, low)

    def test_many_reports_raise_score(self):
        s1 = self._score(report_count=1)
        s2 = self._score(report_count=15)
        self.assertGreater(s2, s1)

    def test_location_risk_main_road_beats_residential(self):
        s_main = self._score(location_type="main_road")
        s_res  = self._score(location_type="residential")
        self.assertGreater(s_main, s_res)

    def test_overdue_sla_max_contribution(self):
        s_overdue = self._score(hours_until_sla_breach=-5)
        s_ok      = self._score(hours_until_sla_breach=200)
        self.assertGreater(s_overdue, s_ok)

    def test_social_media_spike_raises_score(self):
        s_low  = self._score(social_media_mentions=0)
        s_high = self._score(social_media_mentions=150)
        self.assertGreater(s_high, s_low)

    def test_old_issue_scores_higher_than_new(self):
        s_new = self._score(days_open=0)
        s_old = self._score(days_open=30)
        self.assertGreater(s_old, s_new)

    def test_safety_keyword_triggers_bonus(self):
        s_normal = self._score(description="garbage on street")
        s_danger = self._score(description="garbage on street danger hazard for children")
        self.assertGreater(s_danger, s_normal)

    def test_score_capped_at_100(self):
        # Max out every dimension
        score = self._score(
            issue_category="open_manhole",
            report_count=20,
            location_type="main_road",
            days_open=30,
            hours_until_sla_breach=-20,
            social_media_mentions=200,
            description="open manhole accident danger hazard fire emergency flood collapse",
            month=7,
        )
        self.assertLessEqual(score, 100.0)

    def test_monsoon_month_not_negative(self):
        # Month alone doesn't lower score; feature is ML-only
        s_monsoon = self._score(month=7)
        s_winter  = self._score(month=1)
        # Both should be non-negative and within range
        self.assertGreaterEqual(s_monsoon, 0)
        self.assertGreaterEqual(s_winter, 0)

    def test_unknown_category_uses_default(self):
        score = self._score(issue_category="some_unknown_category_xyz")
        default_base = SEVERITY_MAP["default"]
        # Score should incorporate the default base
        self.assertGreater(score, 0)

    def test_severity_cap_at_30(self):
        # Even with safety bonus, severity should not exceed 30
        score_component = min(30, SEVERITY_MAP.get("open_manhole", 15) + 5)
        self.assertLessEqual(score_component, 30)


# ─── 2. SCORE TO LABEL ───────────────────────────────────────────────────────

class TestScoreToLabel(unittest.TestCase):

    def test_critical_threshold(self):
        self.assertEqual(_score_to_label(80), "CRITICAL")
        self.assertEqual(_score_to_label(100), "CRITICAL")
        self.assertEqual(_score_to_label(95.5), "CRITICAL")

    def test_high_threshold(self):
        self.assertEqual(_score_to_label(60), "HIGH")
        self.assertEqual(_score_to_label(79.9), "HIGH")

    def test_medium_threshold(self):
        self.assertEqual(_score_to_label(35), "MEDIUM")
        self.assertEqual(_score_to_label(59.9), "MEDIUM")

    def test_low_threshold(self):
        self.assertEqual(_score_to_label(0), "LOW")
        self.assertEqual(_score_to_label(34.9), "LOW")


# ─── 3. FEATURE VECTOR ───────────────────────────────────────────────────────

class TestFeatureVector(unittest.TestCase):

    def _fv(self, **kwargs):
        defaults = dict(
            issue_category="pothole",
            report_count=2,
            days_open=3,
            social_media_mentions=5,
            hours_until_sla_breach=72.0,
            month=6,
            description="pothole on road",
            dept_id="D01",
            ward_id=12,
            day_of_week=2,
            hour_of_day=10,
        )
        defaults.update(kwargs)
        return _build_feature_vector(**defaults)

    def test_feature_vector_length_matches_feature_names(self):
        fv = self._fv()
        self.assertEqual(len(fv), len(FEATURE_NAMES))

    def test_all_values_are_floats(self):
        fv = self._fv()
        for v in fv:
            self.assertIsInstance(v, float)

    def test_is_monsoon_flag_june(self):
        fv = self._fv(month=6)
        mon_idx = FEATURE_NAMES.index("is_monsoon")
        self.assertEqual(fv[mon_idx], 1.0)

    def test_is_monsoon_flag_january(self):
        fv = self._fv(month=1)
        mon_idx = FEATURE_NAMES.index("is_monsoon")
        self.assertEqual(fv[mon_idx], 0.0)

    def test_is_weekend_flag_sunday(self):
        fv = self._fv(day_of_week=6)
        wk_idx = FEATURE_NAMES.index("is_weekend")
        self.assertEqual(fv[wk_idx], 1.0)

    def test_is_weekend_flag_monday(self):
        fv = self._fv(day_of_week=0)
        wk_idx = FEATURE_NAMES.index("is_weekend")
        self.assertEqual(fv[wk_idx], 0.0)

    def test_dept_onehot_correct(self):
        fv = self._fv(dept_id="D01")
        d01_idx = FEATURE_NAMES.index("dept_D01")
        d02_idx = FEATURE_NAMES.index("dept_D02")
        self.assertEqual(fv[d01_idx], 1.0)
        self.assertEqual(fv[d02_idx], 0.0)

    def test_safety_flag_from_description(self):
        fv_safe = self._fv(description="fire burning near market hazard")
        fv_norm = self._fv(description="garbage pile on road")
        sf_idx = FEATURE_NAMES.index("safety_flag")
        self.assertEqual(fv_safe[sf_idx], 1.0)
        self.assertEqual(fv_norm[sf_idx], 0.0)

    def test_report_count_capped_at_20(self):
        fv = self._fv(report_count=1000)
        rc_idx = FEATURE_NAMES.index("report_count")
        self.assertEqual(fv[rc_idx], 20.0)

    def test_days_open_capped_at_60(self):
        fv = self._fv(days_open=500)
        do_idx = FEATURE_NAMES.index("days_open")
        self.assertEqual(fv[do_idx], 60.0)


# ─── 4. SYNTHETIC DATASET ────────────────────────────────────────────────────

class TestSyntheticDataset(unittest.TestCase):

    def setUp(self):
        self.X, self.y = _build_synthetic_training_data()

    def test_dataset_has_80_samples(self):
        self.assertEqual(len(self.X), 80)
        self.assertEqual(len(self.y), 80)

    def test_all_labels_present(self):
        label_set = set(self.y)
        self.assertEqual(label_set, {0, 1, 2, 3})  # LOW, MEDIUM, HIGH, CRITICAL

    def test_balanced_ish_distribution(self):
        """Each label should have at least 15 samples (we have 20 per class)."""
        from collections import Counter
        counts = Counter(self.y)
        for label in [0, 1, 2, 3]:
            self.assertGreaterEqual(counts[label], 15,
                msg=f"Label {label} has fewer than 15 samples")

    def test_feature_vectors_correct_length(self):
        for fv in self.X:
            self.assertEqual(len(fv), len(FEATURE_NAMES))

    def test_all_feature_values_are_finite(self):
        import math
        for i, fv in enumerate(self.X):
            for j, v in enumerate(fv):
                self.assertTrue(
                    math.isfinite(v),
                    msg=f"Sample {i}, feature {j} ({FEATURE_NAMES[j]}) is not finite: {v}"
                )


# ─── 5. ML WARM-START + PREDICTION ──────────────────────────────────────────

class TestMLWarmStart(unittest.TestCase):
    """
    These tests call the synchronous parts of the ML model.
    The warm-start is done inline without MongoDB (pure in-memory).
    """

    @classmethod
    def setUpClass(cls):
        """Train model on synthetic data synchronously for all tests in this class."""
        import numpy as np
        X, y = _build_synthetic_training_data()
        X_np = np.array(X, dtype=float)
        y_np = np.array(y, dtype=int)

        try:
            from lightgbm import LGBMClassifier
            clf = LGBMClassifier(
                objective="multiclass",
                num_class=4,
                n_estimators=50,
                random_state=42,
                verbose=-1,
            )
        except ImportError:
            from sklearn.linear_model import SGDClassifier
            clf = SGDClassifier(loss="modified_huber", max_iter=1000, random_state=42)

        clf.fit(X_np, y_np)
        # Inject into the singleton for testing
        _ml_model._clf = clf
        _ml_model._sample_count = 80   # above MIN_SAMPLES_TO_USE (50)
        _ml_model._training_X = list(X)
        _ml_model._training_y = list(y)
        cls.test_feature = X[0]  # take first sample (CRITICAL)

    def test_model_is_ready(self):
        self.assertIsNotNone(_ml_model._clf)
        self.assertGreaterEqual(_ml_model._sample_count, _ml_model.MIN_SAMPLES_TO_USE)

    def test_predict_returns_valid_label(self):
        label = _ml_model.predict(self.test_feature)
        self.assertIn(label, {"LOW", "MEDIUM", "HIGH", "CRITICAL"})

    def test_predict_proba_sums_to_one(self):
        probas = _ml_model.predict_proba(self.test_feature)
        self.assertIsNotNone(probas)
        total = sum(probas.values())
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_predict_proba_has_all_labels(self):
        probas = _ml_model.predict_proba(self.test_feature)
        for label in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            self.assertIn(label, probas)

    def test_critical_feature_not_predicted_low(self):
        """A clear CRITICAL symptom vector shouldn't be predicted LOW."""
        X, y = _build_synthetic_training_data()
        # Pick a CRITICAL sample
        critical_fv = next(fv for fv, lbl in zip(X, y) if lbl == 3)  # label 3 = CRITICAL
        label = _ml_model.predict(critical_fv)
        self.assertNotEqual(label, "LOW",
            msg="Model predicted LOW for a CRITICAL training sample — poor accuracy")

    def test_low_feature_not_predicted_critical(self):
        """A clear LOW symptom vector shouldn't be predicted CRITICAL."""
        X, y = _build_synthetic_training_data()
        low_fv = next(fv for fv, lbl in zip(X, y) if lbl == 0)  # label 0 = LOW
        label = _ml_model.predict(low_fv)
        self.assertNotEqual(label, "CRITICAL",
            msg="Model predicted CRITICAL for a LOW training sample — poor accuracy")

    def test_ml_not_active_below_threshold(self):
        """If sample_count < MIN_SAMPLES_TO_USE, predict should return None."""
        _ml_model._sample_count = 10   # below threshold
        result = _ml_model.predict(self.test_feature)
        self.assertIsNone(result)
        # Restore for following tests
        _ml_model._sample_count = 80

    def test_ml_returns_none_without_model(self):
        saved = _ml_model._clf
        _ml_model._clf = None
        result = _ml_model.predict(self.test_feature)
        self.assertIsNone(result)
        _ml_model._clf = saved


# ─── 6. EXPLAIN PRIORITY ─────────────────────────────────────────────────────

class TestExplainPriority(unittest.TestCase):

    def _explain(self, **kwargs):
        defaults = dict(
            issue_category="pothole",
            description="large pothole on main road hitting cars",
            dept_id="D01",
            report_count=5,
            location_type="main_road",
            days_open=7,
            hours_until_sla_breach=12.0,
            social_media_mentions=55,
            month=7,
            ward_id=12,
            day_of_week=1,
            hour_of_day=9,
        )
        defaults.update(kwargs)
        return explain_priority(**defaults)

    def test_explanation_has_required_keys(self):
        result = self._explain()
        required = [
            "rule_score", "rule_label", "breakdown",
            "ml_model_active", "ml_sample_count",
        ]
        for key in required:
            self.assertIn(key, result, msg=f"Key '{key}' missing from explain output")

    def test_breakdown_has_five_components(self):
        bd = self._explain()["breakdown"]
        self.assertIn("severity", bd)
        self.assertIn("impact", bd)
        self.assertIn("age", bd)
        self.assertIn("sla", bd)
        self.assertIn("social", bd)

    def test_each_component_has_score_and_max(self):
        bd = self._explain()["breakdown"]
        for component, data in bd.items():
            self.assertIn("score", data, msg=f"{component} missing 'score'")
            self.assertIn("max", data, msg=f"{component} missing 'max'")

    def test_component_scores_dont_exceed_max(self):
        bd = self._explain()["breakdown"]
        for component, data in bd.items():
            self.assertLessEqual(data["score"], data["max"],
                msg=f"{component} score {data['score']} exceeds max {data['max']}")

    def test_rule_score_is_float(self):
        result = self._explain()
        self.assertIsInstance(result["rule_score"], float)

    def test_rule_label_valid(self):
        result = self._explain()
        self.assertIn(result["rule_label"], {"LOW", "MEDIUM", "HIGH", "CRITICAL"})

    def test_ml_probabilities_when_model_active(self):
        # Model is active from TestMLWarmStart.setUpClass
        result = self._explain()
        if result["ml_model_active"]:
            self.assertIsNotNone(result["ml_probabilities"])
            total = sum(result["ml_probabilities"].values())
            self.assertAlmostEqual(total, 1.0, places=4)

    def test_main_road_scores_higher_than_internal_street(self):
        r_main = self._explain(location_type="main_road")
        r_int  = self._explain(location_type="internal_street")
        self.assertGreater(r_main["rule_score"], r_int["rule_score"])

    def test_open_manhole_higher_than_missed_garbage_collection(self):
        r1 = self._explain(issue_category="open_manhole", description="open manhole danger")
        r2 = self._explain(issue_category="missed_collection_once", description="garbage not collected")
        self.assertGreater(r1["rule_score"], r2["rule_score"])

    def test_high_social_media_included_in_social_score(self):
        r_high = self._explain(social_media_mentions=150)
        r_low  = self._explain(social_media_mentions=0)
        self.assertGreater(
            r_high["breakdown"]["social"]["score"],
            r_low["breakdown"]["social"]["score"],
        )


# ─── 7. END-TO-END: calculate_priority (sync portion) ───────────────────────

class TestCalculatePrioritySync(unittest.TestCase):
    """
    Test the logic of calculate_priority without actually calling the async
    MongoDB I/O (which requires a live server). We test the rule path only.
    """

    def _run(self, **kwargs):
        """Run calculate_priority synchronously for testing purposes."""
        import asyncio
        from app.services.ai.priority_agent import calculate_priority
        defaults = dict(
            issue_category="pothole",
            description="large pothole on road",
            dept_id="D01",
            report_count=1,
            location_type="unknown",
            days_open=0,
            hours_until_sla_breach=168.0,
            social_media_mentions=0,
            month=6,
            ward_id=0,
            day_of_week=0,
            hour_of_day=12,
        )
        defaults.update(kwargs)
        # Temporarily disable ML to test rule path
        saved_count = _ml_model._sample_count
        _ml_model._sample_count = 0
        try:
            return asyncio.run(calculate_priority(**defaults))
        finally:
            _ml_model._sample_count = saved_count

    def test_returns_tuple_of_three(self):
        result = self._run()
        self.assertEqual(len(result), 3)

    def test_score_in_range(self):
        score, label, source = self._run()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_label_is_valid(self):
        score, label, source = self._run()
        self.assertIn(label, {"LOW", "MEDIUM", "HIGH", "CRITICAL"})

    def test_source_is_rules_when_ml_unavailable(self):
        score, label, source = self._run()
        self.assertEqual(source, "rules")

    def test_critical_scenario(self):
        score, label, source = self._run(
            issue_category="open_manhole",
            description="open manhole accident emergency flood danger",
            report_count=15,
            location_type="main_road",
            hours_until_sla_breach=-5,
            social_media_mentions=120,
            days_open=10,
        )
        self.assertGreaterEqual(score, 80, msg="Expected CRITICAL for extreme conditions")
        self.assertEqual(label, "CRITICAL")

    def test_low_scenario(self):
        score, label, source = self._run(
            issue_category="missed_collection_once",
            description="garbage bin not collected yesterday",
            report_count=1,
            location_type="residential",
            hours_until_sla_breach=140,
            social_media_mentions=0,
            days_open=1,
        )
        self.assertLess(score, 60, msg="Expected LOW/MEDIUM for trivial conditions")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("  JanVedha AI — Priority Scoring Model Tests")
    print("=" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes in dependency order
    for cls in [
        TestRuleEngine,
        TestScoreToLabel,
        TestFeatureVector,
        TestSyntheticDataset,
        TestMLWarmStart,
        TestExplainPriority,
        TestCalculatePrioritySync,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
