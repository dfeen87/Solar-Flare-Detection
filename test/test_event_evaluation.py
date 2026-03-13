"""
test_event_evaluation.py — Deterministic unit tests for shared/event_evaluation.py.

Tests cover:
  (A) Lead-time correctness (first crossing + max mode + tie-breaking)
  (B) Flare-aligned window extraction
  (C) Threshold metrics TP/FP/TN/FN
  (D) ROC monotonicity (FPR sorted)
  (E) AUC correctness (exact trapezoid + unsorted input)
"""

import numpy as np
import pandas as pd
import pytest

from shared.event_evaluation import (
    _extract_flare_windows,
    compute_auc,
    compute_lead_times,
    compute_roc,
    compute_threshold_metrics,
)

# ---------------------------------------------------------------------------
# Common base time
# ---------------------------------------------------------------------------
t0 = pd.Timestamp("2026-01-01T00:00:00Z")


# ===================================================================
# (A) Lead-time correctness
# ===================================================================

class TestLeadTimes:
    """First crossing + max mode lead-time computation."""

    def _build_basic_signal(self):
        """Signal pattern: below 0.5 until minute 60, 0.6 at 60, 0.9 at 100."""
        rows = []
        for i in range(121):  # minutes 0..120
            t = t0 + pd.Timedelta(minutes=i)
            if i < 60:
                val = 0.1
            elif i == 60:
                val = 0.6
            elif i == 100:
                val = 0.9
            else:
                val = 0.3
            rows.append({"time": t, "signal": val})
        return pd.DataFrame(rows)

    def test_first_crossing_and_max(self):
        signal_df = self._build_basic_signal()
        flare_df = pd.DataFrame({"onset_time": [t0 + pd.Timedelta(minutes=120)]})

        result = compute_lead_times(signal_df, flare_df, window_hours=24)

        assert len(result) == 1
        row = result.iloc[0]

        # First crossing at minute 60 → lead = 60 min = 1.0 h
        assert row["first_crossing_time"] == t0 + pd.Timedelta(minutes=60)
        assert row["lead_time_first_crossing_hours"] == pytest.approx(1.0)

        # Max signal at minute 100 → lead = 20 min = 1/3 h
        assert row["max_signal_time"] == t0 + pd.Timedelta(minutes=100)
        assert row["lead_time_max_signal_hours"] == pytest.approx(20.0 / 60.0)

    def test_max_tie_breaking_picks_latest(self):
        """When two maxima are equal, pick the latest time."""
        rows = []
        for i in range(121):
            t = t0 + pd.Timedelta(minutes=i)
            if i == 90:
                val = 0.9
            elif i == 100:
                val = 0.9
            elif i == 60:
                val = 0.6
            elif i < 60:
                val = 0.1
            else:
                val = 0.3
            rows.append({"time": t, "signal": val})
        signal_df = pd.DataFrame(rows)
        flare_df = pd.DataFrame({"onset_time": [t0 + pd.Timedelta(minutes=120)]})

        result = compute_lead_times(signal_df, flare_df, window_hours=24)
        row = result.iloc[0]

        # Latest max at minute 100
        assert row["max_signal_time"] == t0 + pd.Timedelta(minutes=100)

    def test_no_samples_gives_nan(self):
        """Empty lookback → NaN lead times."""
        signal_df = pd.DataFrame({"time": [t0], "signal": [0.8]})
        flare_df = pd.DataFrame(
            {"onset_time": [t0 + pd.Timedelta(hours=48)]}
        )  # far away

        result = compute_lead_times(signal_df, flare_df, window_hours=1)
        row = result.iloc[0]
        assert np.isnan(row["lead_time_first_crossing_hours"])
        assert np.isnan(row["lead_time_max_signal_hours"])
        assert pd.isna(row["first_crossing_time"])
        assert pd.isna(row["max_signal_time"])


# ===================================================================
# (B) Flare-aligned window extraction
# ===================================================================

class TestFlareAlignedWindows:
    """Window extraction with right-open interval."""

    def test_window_bounds(self):
        """Window [t_k - W_pre, t_k + W_post) with custom widths."""
        # Build 200 minutes of data
        signal_df = pd.DataFrame(
            {
                "time": [t0 + pd.Timedelta(minutes=i) for i in range(200)],
                "signal": [float(i) for i in range(200)],
            }
        )
        flare_df = pd.DataFrame(
            {"onset_time": [t0 + pd.Timedelta(minutes=120)]}
        )

        windows = _extract_flare_windows(
            signal_df,
            flare_df,
            W_pre=pd.Timedelta(minutes=30),
            W_post=pd.Timedelta(minutes=10),
        )

        assert len(windows) == 1
        win = windows[0]

        # Expected: minutes 90..129 (inclusive of 90, exclusive of 130)
        expected_start = t0 + pd.Timedelta(minutes=90)
        expected_end = t0 + pd.Timedelta(minutes=130)

        assert win["time"].min() == expected_start
        # Right-open: minute 130 should not be present, max is 129
        assert win["time"].max() == expected_end - pd.Timedelta(minutes=1)
        assert len(win) == 40  # minutes 90..129

    def test_onset_excluded_from_pre_window(self):
        """Signal exactly at onset_time must not count as TP (right-open)."""
        # Only sample is at onset_time
        onset = t0 + pd.Timedelta(hours=2)
        signal_df = pd.DataFrame(
            {"time": [onset], "signal": [0.99]}
        )
        flare_df = pd.DataFrame({"onset_time": [onset]})

        metrics = compute_threshold_metrics(signal_df, flare_df, [0.5])
        # The onset sample is not in [onset-24h, onset) pre-window → FN
        assert metrics.iloc[0]["TP"] == 0
        assert metrics.iloc[0]["FN"] == 1


# ===================================================================
# (C) Threshold metrics TP/FP/TN/FN
# ===================================================================

class TestThresholdMetrics:
    """Event-based confusion counts for threshold sweep."""

    def _build_scenario(self):
        """
        2000 minutes of data. Two flares spaced > 24 h apart so their
        pre-windows do not overlap.

        Flare 1 at minute 120 → pre-window [0, 120)   (120 timestamps)
        Flare 2 at minute 1800 → pre-window [360, 1800) (1440 timestamps)
        Union of pre-windows: 0..119  ∪  360..1799
        Non-flare timestamps: 120..359  ∪  1800..1999  → 240 + 200 = 440

        In pre-window of flare 1: minute 100 has signal = 0.8  (TP)
        In pre-window of flare 2: all signal = 0.1              (FN)
        Non-flare region: minutes 200, 210, 220 have signal 0.8 (FP = 3)
        TN = 440 - 3 = 437
        """
        rows = []
        for i in range(2000):
            t = t0 + pd.Timedelta(minutes=i)
            val = 0.1
            if i == 100:
                val = 0.8
            if i in (200, 210, 220):
                val = 0.8
            rows.append({"time": t, "signal": val})

        signal_df = pd.DataFrame(rows)
        flare_df = pd.DataFrame(
            {"onset_time": [
                t0 + pd.Timedelta(minutes=120),
                t0 + pd.Timedelta(minutes=1800),
            ]}
        )
        return signal_df, flare_df

    def test_confusion_counts_at_0_7(self):
        signal_df, flare_df = self._build_scenario()
        metrics = compute_threshold_metrics(signal_df, flare_df, [0.7])
        row = metrics.iloc[0]

        assert row["TP"] == 1   # flare 1 has sample 0.8 >= 0.7
        assert row["FN"] == 1   # flare 2 has no sample >= 0.7 in its pre-window
        assert row["FP"] == 3   # 3 non-flare timestamps >= 0.7
        # Non-flare timestamps: 120..359 ∪ 1800..1999 = 440 timestamps
        # 3 are FP → TN = 437
        assert row["TN"] == 437

    def test_rates(self):
        signal_df, flare_df = self._build_scenario()
        metrics = compute_threshold_metrics(signal_df, flare_df, [0.7])
        row = metrics.iloc[0]

        assert row["TPR"] == pytest.approx(0.5)       # 1/2
        assert row["FNR"] == pytest.approx(0.5)       # 1/2
        assert row["FPR"] == pytest.approx(3.0 / 440) # 3/440
        assert row["TNR"] == pytest.approx(437.0 / 440)


# ===================================================================
# (D) ROC monotonicity
# ===================================================================

class TestROC:
    """ROC curve data generation with FPR sorting."""

    def test_fpr_non_decreasing(self):
        """Intentionally unsorted thresholds → sorted FPR output."""
        # Build a small dataset
        signal_df = pd.DataFrame(
            {
                "time": [t0 + pd.Timedelta(minutes=i) for i in range(200)],
                "signal": np.linspace(0.0, 1.0, 200),
            }
        )
        flare_df = pd.DataFrame(
            {"onset_time": [t0 + pd.Timedelta(minutes=100)]}
        )

        fpr, tpr, thresholds_sorted = compute_roc(
            signal_df, flare_df, [0.9, 0.1, 0.5]
        )

        assert len(fpr) == 3
        assert len(tpr) == 3
        assert len(thresholds_sorted) == 3
        # FPR must be non-decreasing
        assert np.all(np.diff(fpr) >= 0)


# ===================================================================
# (E) AUC correctness
# ===================================================================

class TestAUC:
    """Trapezoidal AUC computation."""

    def test_exact_trapezoid(self):
        fpr = [0.0, 0.5, 1.0]
        tpr = [0.0, 1.0, 1.0]
        assert compute_auc(fpr, tpr) == pytest.approx(0.75)

    def test_unsorted_input(self):
        """Non-monotone FPR is sorted before integration."""
        fpr = [1.0, 0.0, 0.5]
        tpr = [1.0, 0.0, 1.0]
        assert compute_auc(fpr, tpr) == pytest.approx(0.75)

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="1D arrays of the same length"):
            compute_auc([0.0, 1.0], [0.0])

    def test_too_few_points_raises(self):
        with pytest.raises(ValueError, match="1D arrays of the same length"):
            compute_auc([0.0], [0.0])

    def test_nan_handling(self):
        fpr = [0.0, np.nan, 0.5, 1.0]
        tpr = [0.0, np.nan, 1.0, 1.0]
        assert compute_auc(fpr, tpr) == pytest.approx(0.75)


# ===================================================================
# Input validation tests
# ===================================================================

class TestInputValidation:
    """Ensure clear errors on bad input."""

    def test_missing_signal_columns(self):
        with pytest.raises(ValueError, match="signal_df must contain columns"):
            compute_lead_times(
                pd.DataFrame({"t": [1], "s": [1]}),
                pd.DataFrame({"onset_time": [t0]}),
            )

    def test_missing_flare_column(self):
        with pytest.raises(ValueError, match="flare_df must contain column"):
            compute_lead_times(
                pd.DataFrame({"time": [t0], "signal": [0.5]}),
                pd.DataFrame({"start": [t0]}),
            )

    def test_empty_thresholds(self):
        with pytest.raises(ValueError, match="thresholds must be a non-empty"):
            compute_threshold_metrics(
                pd.DataFrame({"time": [t0], "signal": [0.5]}),
                pd.DataFrame({"onset_time": [t0]}),
                [],
            )
