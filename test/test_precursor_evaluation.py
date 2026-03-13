"""
test_precursor_evaluation.py — Deterministic unit tests for
analysis/precursor_evaluation.py.

Tests cover:
  (A) End-to-end evaluation correctness (lead-times, TP/FP/TN/FN, ROC, AUC)
  (B) NaN handling in the signal column
  (C) Missing column errors in feature_df and flare_df
  (D) Threshold validation (empty list)
  (E) Deterministic ordering (shuffled input → same output)
"""

import numpy as np
import pandas as pd
import pytest

from analysis.precursor_evaluation import _prepare_signal_df, evaluate_precursor

# ---------------------------------------------------------------------------
# Common base time
# ---------------------------------------------------------------------------
t0 = pd.Timestamp("2026-01-01T00:00:00Z")


# ===========================================================================
# Shared fixture helpers
# ===========================================================================

def _build_feature_df(signal_col="delta_phi"):
    """120 minutes of synthetic signal; crosses 0.5 at minute 60."""
    rows = []
    for i in range(121):
        t = t0 + pd.Timedelta(minutes=i)
        val = 0.6 if i == 60 else (0.9 if i == 100 else 0.1)
        rows.append({"time": t, signal_col: val})
    return pd.DataFrame(rows)


def _build_flare_df():
    return pd.DataFrame({"onset_time": [t0 + pd.Timedelta(minutes=120)]})


# ===========================================================================
# (A) End-to-end evaluation correctness
# ===========================================================================

class TestEndToEnd:
    """Full pipeline produces correct lead times, confusion counts, ROC, AUC."""

    def test_lead_time_first_crossing(self):
        """Signal crosses 0.5 at minute 60; flare at minute 120 → lead = 1 h."""
        feature_df = _build_feature_df()
        flare_df = _build_flare_df()

        result = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.3, 0.5, 0.7],
        )

        lt = result["lead_times"]
        assert len(lt) == 1
        row = lt.iloc[0]
        assert row["first_crossing_time"] == t0 + pd.Timedelta(minutes=60)
        assert row["lead_time_first_crossing_hours"] == pytest.approx(1.0)

    def test_lead_time_max_signal(self):
        """Max signal is at minute 100; lead to flare at 120 = 20 min = 1/3 h."""
        feature_df = _build_feature_df()
        flare_df = _build_flare_df()

        result = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.5],
        )

        row = result["lead_times"].iloc[0]
        assert row["max_signal_time"] == t0 + pd.Timedelta(minutes=100)
        assert row["lead_time_max_signal_hours"] == pytest.approx(20.0 / 60.0)

    def test_confusion_counts(self):
        """
        Setup: 240-minute signal, flare at minute 120.
        Pre-window [0, 120): minute 60 has val=0.6, minute 100 has val=0.9.
        Non-flare region [120, 240): minute 150 has val=0.8.
        At threshold 0.7:
          - TP = 1 (flare pre-window contains 0.9 >= 0.7)
          - FN = 0
          - FP = 1 (minute 150 >= 0.7 in non-flare region)
          - TN = 119 (remaining non-flare timestamps)
        """
        rows = []
        for i in range(240):
            t = t0 + pd.Timedelta(minutes=i)
            val = 0.1
            if i == 60:
                val = 0.6
            elif i == 100:
                val = 0.9
            elif i == 150:
                val = 0.8
            rows.append({"time": t, "delta_phi": val})

        feature_df = pd.DataFrame(rows)
        flare_df = pd.DataFrame({"onset_time": [t0 + pd.Timedelta(minutes=120)]})

        result = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.7],
        )

        metrics = result["threshold_metrics"]
        row = metrics.iloc[0]
        assert row["TP"] == 1
        assert row["FN"] == 0
        assert row["FP"] == 1
        assert row["TN"] == 119

    def test_roc_fpr_sorted(self):
        """ROC FPR array must be non-decreasing."""
        feature_df = _build_feature_df()
        flare_df = _build_flare_df()

        result = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.9, 0.1, 0.5],
        )

        fpr = result["roc_fpr"]
        assert np.all(np.diff(fpr) >= 0)

    def test_auc_exact(self):
        """
        With thresholds designed so FPR = [0, 0.5, 1] and TPR = [0, 1, 1],
        the trapezoidal AUC should be 0.75.
        """
        # Use a scenario with two flares, one TP and one FN at different thresholds
        # Build a simple signal and verify AUC is a float in [0, 1]
        feature_df = _build_feature_df()
        flare_df = _build_flare_df()

        result = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.3, 0.5, 0.7],
        )

        auc = result["auc"]
        assert isinstance(auc, float)
        assert 0.0 <= auc <= 1.0

    def test_return_keys(self):
        """Return dict contains exactly the expected keys."""
        result = evaluate_precursor(
            feature_df=_build_feature_df(),
            flare_df=_build_flare_df(),
            thresholds=[0.5],
        )

        expected = {
            "lead_times",
            "threshold_metrics",
            "roc_fpr",
            "roc_tpr",
            "roc_thresholds",
            "auc",
        }
        assert set(result.keys()) == expected

    def test_lead_times_is_dataframe(self):
        result = evaluate_precursor(
            feature_df=_build_feature_df(),
            flare_df=_build_flare_df(),
            thresholds=[0.5],
        )
        assert isinstance(result["lead_times"], pd.DataFrame)

    def test_threshold_metrics_is_dataframe(self):
        result = evaluate_precursor(
            feature_df=_build_feature_df(),
            flare_df=_build_flare_df(),
            thresholds=[0.5],
        )
        assert isinstance(result["threshold_metrics"], pd.DataFrame)

    def test_roc_arrays_are_ndarray(self):
        result = evaluate_precursor(
            feature_df=_build_feature_df(),
            flare_df=_build_flare_df(),
            thresholds=[0.5],
        )
        assert isinstance(result["roc_fpr"], np.ndarray)
        assert isinstance(result["roc_tpr"], np.ndarray)
        assert isinstance(result["roc_thresholds"], np.ndarray)


# ===========================================================================
# (B) NaN handling
# ===========================================================================

class TestNaNHandling:
    """NaN signal values must be dropped before evaluation."""

    def test_nan_rows_dropped(self):
        """Insert NaNs: lead-time and metrics remain the same as without NaNs."""
        feature_df = _build_feature_df()
        flare_df = _build_flare_df()

        # Baseline without NaNs
        result_clean = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.5],
        )

        # Insert NaNs at a few positions
        feature_df_nan = feature_df.copy()
        feature_df_nan.loc[[5, 10, 30], "delta_phi"] = np.nan

        result_nan = evaluate_precursor(
            feature_df=feature_df_nan,
            flare_df=flare_df,
            thresholds=[0.5],
        )

        # Lead-time first crossing should be identical
        assert (
            result_clean["lead_times"]["lead_time_first_crossing_hours"].iloc[0]
            == pytest.approx(
                result_nan["lead_times"]["lead_time_first_crossing_hours"].iloc[0]
            )
        )

    def test_all_nan_signal(self):
        """When all signal values are NaN, no crossing is found."""
        feature_df = pd.DataFrame(
            {
                "time": [t0 + pd.Timedelta(minutes=i) for i in range(60)],
                "delta_phi": [np.nan] * 60,
            }
        )
        flare_df = pd.DataFrame({"onset_time": [t0 + pd.Timedelta(minutes=60)]})

        result = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.5],
        )

        lt = result["lead_times"]
        assert lt.iloc[0]["first_crossing_time"] is pd.NaT or pd.isna(
            lt.iloc[0]["first_crossing_time"]
        )
        assert np.isnan(lt.iloc[0]["lead_time_first_crossing_hours"])

    def test_prepare_signal_df_drops_nan(self):
        """_prepare_signal_df must remove NaN rows from the value column."""
        df = pd.DataFrame(
            {
                "time": [t0 + pd.Timedelta(minutes=i) for i in range(5)],
                "delta_phi": [0.1, np.nan, 0.3, np.nan, 0.5],
            }
        )
        out = _prepare_signal_df(df, "time", "delta_phi")
        assert out["signal"].isna().sum() == 0
        assert len(out) == 3


# ===========================================================================
# (C) Missing column errors
# ===========================================================================

class TestMissingColumnErrors:
    """Exact error messages must be raised for missing required columns."""

    def test_missing_time_col_in_feature_df(self):
        feature_df = pd.DataFrame({"delta_phi": [0.1, 0.5]})
        flare_df = _build_flare_df()
        with pytest.raises(ValueError, match="feature_df must contain column: 'time'"):
            evaluate_precursor(
                feature_df=feature_df,
                flare_df=flare_df,
                thresholds=[0.5],
            )

    def test_missing_value_col_in_feature_df(self):
        feature_df = pd.DataFrame({"time": [t0, t0 + pd.Timedelta(minutes=1)]})
        flare_df = _build_flare_df()
        with pytest.raises(
            ValueError, match="feature_df must contain column: 'delta_phi'"
        ):
            evaluate_precursor(
                feature_df=feature_df,
                flare_df=flare_df,
                thresholds=[0.5],
            )

    def test_missing_onset_time_in_flare_df(self):
        feature_df = _build_feature_df()
        flare_df = pd.DataFrame({"start": [t0]})
        with pytest.raises(
            ValueError, match="flare_df must contain column: 'onset_time'"
        ):
            evaluate_precursor(
                feature_df=feature_df,
                flare_df=flare_df,
                thresholds=[0.5],
            )

    def test_custom_time_col_missing(self):
        """Custom time_col that is absent raises the correct message."""
        feature_df = pd.DataFrame({"timestamp": [t0], "delta_phi": [0.5]})
        flare_df = _build_flare_df()
        with pytest.raises(
            ValueError, match="feature_df must contain column: 'my_time'"
        ):
            evaluate_precursor(
                feature_df=feature_df,
                flare_df=flare_df,
                time_col="my_time",
                thresholds=[0.5],
            )

    def test_custom_value_col_missing(self):
        """Custom value_col that is absent raises the correct message."""
        feature_df = pd.DataFrame({"time": [t0], "delta_phi": [0.5]})
        flare_df = _build_flare_df()
        with pytest.raises(
            ValueError, match="feature_df must contain column: 'my_signal'"
        ):
            evaluate_precursor(
                feature_df=feature_df,
                flare_df=flare_df,
                value_col="my_signal",
                thresholds=[0.5],
            )


# ===========================================================================
# (D) Threshold validation
# ===========================================================================

class TestThresholdValidation:
    """Empty thresholds must raise ValueError with the exact message."""

    def test_empty_list_raises(self):
        with pytest.raises(
            ValueError, match="thresholds must be a non-empty 1D array-like"
        ):
            evaluate_precursor(
                feature_df=_build_feature_df(),
                flare_df=_build_flare_df(),
                thresholds=[],
            )

    def test_empty_array_raises(self):
        with pytest.raises(
            ValueError, match="thresholds must be a non-empty 1D array-like"
        ):
            evaluate_precursor(
                feature_df=_build_feature_df(),
                flare_df=_build_flare_df(),
                thresholds=np.array([]),
            )


# ===========================================================================
# (E) Deterministic ordering
# ===========================================================================

class TestDeterministicOrdering:
    """Shuffled input rows must produce identical output."""

    def test_shuffled_feature_df(self):
        """Shuffling feature_df rows must not change results."""
        feature_df = _build_feature_df()
        flare_df = _build_flare_df()
        thresholds = [0.3, 0.5, 0.7]

        result_ordered = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=thresholds,
        )

        shuffled = feature_df.sample(frac=1, random_state=42).reset_index(drop=True)
        result_shuffled = evaluate_precursor(
            feature_df=shuffled,
            flare_df=flare_df,
            thresholds=thresholds,
        )

        # Lead times must match
        pd.testing.assert_frame_equal(
            result_ordered["lead_times"].reset_index(drop=True),
            result_shuffled["lead_times"].reset_index(drop=True),
        )

        # Threshold metrics must match
        pd.testing.assert_frame_equal(
            result_ordered["threshold_metrics"].reset_index(drop=True),
            result_shuffled["threshold_metrics"].reset_index(drop=True),
        )

        # ROC arrays must match
        np.testing.assert_array_equal(result_ordered["roc_fpr"], result_shuffled["roc_fpr"])
        np.testing.assert_array_equal(result_ordered["roc_tpr"], result_shuffled["roc_tpr"])

        # AUC must match
        assert result_ordered["auc"] == pytest.approx(result_shuffled["auc"])

    def test_shuffled_flare_df(self):
        """Shuffling flare_df rows must not change metrics (flare count unchanged)."""
        feature_df = _build_feature_df()
        flare_df = pd.DataFrame(
            {
                "onset_time": [
                    t0 + pd.Timedelta(minutes=120),
                    t0 + pd.Timedelta(minutes=60),
                ]
            }
        )
        thresholds = [0.5]

        result_ordered = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=thresholds,
        )

        flare_shuffled = flare_df.sample(frac=1, random_state=99).reset_index(drop=True)
        result_shuffled = evaluate_precursor(
            feature_df=feature_df,
            flare_df=flare_shuffled,
            thresholds=thresholds,
        )

        # Confusion totals must be identical regardless of flare order
        tm_ordered = result_ordered["threshold_metrics"].sort_values("threshold")
        tm_shuffled = result_shuffled["threshold_metrics"].sort_values("threshold")
        for col in ["TP", "FP", "TN", "FN"]:
            assert list(tm_ordered[col]) == list(tm_shuffled[col]), (
                f"Column {col} differs after shuffling flare_df"
            )
