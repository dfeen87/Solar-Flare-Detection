"""
test_shuffle_test.py — Deterministic unit tests for
analysis/shuffle_test.py.

Tests cover:
  (A) Basic correctness: real AUC > shuffled AUC → p-value < 0.05
  (B) Deterministic behaviour: same seed → identical; different seed → different
  (C) Missing column errors: time_col, value_col, onset_time
  (D) NaN handling: NaNs dropped before shuffling; all-NaN → ValueError
  (E) n_shuffles validation: n_shuffles <= 0 → ValueError
"""

import numpy as np
import pandas as pd
import pytest

from analysis.shuffle_test import run_shuffle_test

# ---------------------------------------------------------------------------
# Base time anchor
# ---------------------------------------------------------------------------
t0 = pd.Timestamp("2026-01-01T00:00:00Z")


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _build_strong_signal_df(n_minutes: int = 300, signal_col: str = "delta_phi"):
    """Build a synthetic signal where pre-flare minutes carry high values.

    Structure
    ---------
    - Minutes 0–299: signal defaults to 0.05 (background noise)
    - Minutes 220–299 (pre-flare window before flare at 300): signal = 0.9
    - Flare onset at minute 300
    """
    rows = []
    for i in range(n_minutes):
        t = t0 + pd.Timedelta(minutes=i)
        val = 0.9 if i >= 220 else 0.05
        rows.append({"time": t, signal_col: val})
    return pd.DataFrame(rows)


def _build_flare_df():
    """Single flare at minute 300."""
    return pd.DataFrame({"onset_time": [t0 + pd.Timedelta(minutes=300)]})


def _build_thresholds():
    return np.linspace(0.0, 1.0, 20)


# ===========================================================================
# (A) Basic correctness
# ===========================================================================

class TestBasicCorrectness:
    """Real AUC > shuffled AUC on a strong synthetic signal → p_value < 0.05."""

    def test_p_value_below_threshold(self):
        """For a strong structured signal the p-value should be < 0.05."""
        feature_df = _build_strong_signal_df()
        flare_df = _build_flare_df()
        thresholds = _build_thresholds()

        result = run_shuffle_test(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=thresholds,
            n_shuffles=200,
            random_state=0,
        )

        assert result["p_value"] < 0.05, (
            f"Expected p_value < 0.05 for strong signal; got {result['p_value']}"
        )

    def test_return_keys(self):
        """Return dict must contain exactly real_auc, shuffle_aucs, p_value."""
        result = run_shuffle_test(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=10,
            random_state=1,
        )
        assert set(result.keys()) == {"real_auc", "shuffle_aucs", "p_value"}

    def test_shuffle_aucs_shape(self):
        """shuffle_aucs must have shape (n_shuffles,)."""
        n = 15
        result = run_shuffle_test(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=n,
            random_state=2,
        )
        assert result["shuffle_aucs"].shape == (n,)

    def test_p_value_in_unit_interval(self):
        """p_value must be in [0.0, 1.0]."""
        result = run_shuffle_test(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=20,
            random_state=3,
        )
        assert 0.0 <= result["p_value"] <= 1.0

    def test_real_auc_is_float(self):
        """real_auc must be a Python float (or numpy scalar castable to float)."""
        result = run_shuffle_test(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=10,
            random_state=4,
        )
        assert isinstance(result["real_auc"], (float, np.floating))

    def test_p_value_definition(self):
        """p_value == fraction of shuffle_aucs >= real_auc."""
        result = run_shuffle_test(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=50,
            random_state=5,
        )
        expected = float(np.mean(result["shuffle_aucs"] >= result["real_auc"]))
        assert result["p_value"] == pytest.approx(expected)


# ===========================================================================
# (B) Deterministic behaviour
# ===========================================================================

class TestDeterministicBehaviour:
    """Same random_state → identical; different random_state → different."""

    def test_same_seed_identical_shuffle_aucs(self):
        """Two calls with the same random_state must produce identical shuffle_aucs."""
        kwargs = dict(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=30,
            random_state=42,
        )
        r1 = run_shuffle_test(**kwargs)
        r2 = run_shuffle_test(**kwargs)
        np.testing.assert_array_equal(r1["shuffle_aucs"], r2["shuffle_aucs"])

    def test_different_seed_different_shuffle_aucs(self):
        """Two calls with different random_states should not be identical."""
        base = dict(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=50,
        )
        r1 = run_shuffle_test(**base, random_state=0)
        r2 = run_shuffle_test(**base, random_state=99)
        assert not np.array_equal(r1["shuffle_aucs"], r2["shuffle_aucs"]), (
            "Different seeds should produce different shuffle AUC distributions"
        )

    def test_same_seed_identical_p_value(self):
        """p_value is deterministic given the same seed."""
        kwargs = dict(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=30,
            random_state=7,
        )
        r1 = run_shuffle_test(**kwargs)
        r2 = run_shuffle_test(**kwargs)
        assert r1["p_value"] == r2["p_value"]

    def test_no_mutation_of_feature_df(self):
        """run_shuffle_test must not mutate the caller's feature_df."""
        feature_df = _build_strong_signal_df()
        original = feature_df.copy(deep=True)
        run_shuffle_test(
            feature_df=feature_df,
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=5,
            random_state=10,
        )
        pd.testing.assert_frame_equal(feature_df, original)

    def test_no_mutation_of_flare_df(self):
        """run_shuffle_test must not mutate the caller's flare_df."""
        flare_df = _build_flare_df()
        original = flare_df.copy(deep=True)
        run_shuffle_test(
            feature_df=_build_strong_signal_df(),
            flare_df=flare_df,
            thresholds=_build_thresholds(),
            n_shuffles=5,
            random_state=11,
        )
        pd.testing.assert_frame_equal(flare_df, original)


# ===========================================================================
# (C) Missing column errors
# ===========================================================================

class TestMissingColumnErrors:
    """Exact error messages for missing columns."""

    def test_missing_time_col_default(self):
        """Missing default time_col 'time' raises correct ValueError."""
        df = pd.DataFrame({"bad_col": [1.0], "delta_phi": [0.5]})
        with pytest.raises(ValueError, match="feature_df must contain column: 'time'"):
            run_shuffle_test(
                feature_df=df,
                flare_df=_build_flare_df(),
                thresholds=[0.5],
            )

    def test_missing_time_col_custom(self):
        """Missing custom time_col raises correct ValueError."""
        df = pd.DataFrame({"time": [t0], "delta_phi": [0.5]})
        with pytest.raises(ValueError, match="feature_df must contain column: 'ts'"):
            run_shuffle_test(
                feature_df=df,
                flare_df=_build_flare_df(),
                thresholds=[0.5],
                time_col="ts",
            )

    def test_missing_value_col_default(self):
        """Missing default value_col 'delta_phi' raises correct ValueError."""
        df = pd.DataFrame({"time": [t0], "bad_col": [0.5]})
        with pytest.raises(ValueError, match="feature_df must contain column: 'delta_phi'"):
            run_shuffle_test(
                feature_df=df,
                flare_df=_build_flare_df(),
                thresholds=[0.5],
            )

    def test_missing_value_col_custom(self):
        """Missing custom value_col raises correct ValueError."""
        df = pd.DataFrame({"time": [t0], "delta_phi": [0.5]})
        with pytest.raises(ValueError, match="feature_df must contain column: 'flux'"):
            run_shuffle_test(
                feature_df=df,
                flare_df=_build_flare_df(),
                thresholds=[0.5],
                value_col="flux",
            )

    def test_missing_flare_onset_time(self):
        """flare_df missing 'onset_time' raises correct ValueError."""
        flare_df = pd.DataFrame({"bad_col": [t0]})
        with pytest.raises(ValueError, match="flare_df must contain column: 'onset_time'"):
            run_shuffle_test(
                feature_df=_build_strong_signal_df(),
                flare_df=flare_df,
                thresholds=[0.5],
            )


# ===========================================================================
# (D) NaN handling
# ===========================================================================

class TestNaNHandling:
    """NaNs are dropped before shuffling; all-NaN → ValueError."""

    def test_nans_dropped_before_shuffling(self):
        """NaN rows are silently dropped; result has the correct shape."""
        # Signal: 400 minutes, flare at minute 200 (so minutes 200-399 are
        # non-flare, giving the ROC enough data for a meaningful AUC).
        flare_at = t0 + pd.Timedelta(minutes=200)
        rows = []
        for i in range(400):
            t = t0 + pd.Timedelta(minutes=i)
            if i % 10 == 0:
                rows.append({"time": t, "delta_phi": np.nan})
            else:
                # High signal in pre-flare window, low elsewhere
                val = 0.9 if 120 <= i < 200 else 0.05
                rows.append({"time": t, "delta_phi": val})
        feature_df = pd.DataFrame(rows)
        flare_df = pd.DataFrame({"onset_time": [flare_at]})

        result = run_shuffle_test(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=_build_thresholds(),
            n_shuffles=20,
            random_state=20,
        )
        # Function must complete without error and return the correct shape.
        assert result["shuffle_aucs"].shape == (20,)
        assert 0.0 <= result["p_value"] <= 1.0

    def test_all_nan_signal_raises(self):
        """All-NaN signal column raises ValueError."""
        feature_df = pd.DataFrame({
            "time": [t0 + pd.Timedelta(minutes=i) for i in range(10)],
            "delta_phi": [np.nan] * 10,
        })
        with pytest.raises(ValueError, match="only NaN values"):
            run_shuffle_test(
                feature_df=feature_df,
                flare_df=_build_flare_df(),
                thresholds=[0.5],
            )

    def test_original_df_not_mutated_with_nans(self):
        """DataFrame with NaN rows must not be mutated after the call."""
        rows = [{"time": t0 + pd.Timedelta(minutes=i), "delta_phi": np.nan if i < 5 else 0.5}
                for i in range(50)]
        feature_df = pd.DataFrame(rows)
        original = feature_df.copy(deep=True)
        flare_df = pd.DataFrame({"onset_time": [t0 + pd.Timedelta(minutes=50)]})

        run_shuffle_test(
            feature_df=feature_df,
            flare_df=flare_df,
            thresholds=[0.4],
            n_shuffles=5,
            random_state=21,
        )
        pd.testing.assert_frame_equal(feature_df, original)


# ===========================================================================
# (E) n_shuffles validation
# ===========================================================================

class TestNShufflesValidation:
    """n_shuffles <= 0 raises ValueError."""

    def test_zero_shuffles_raises(self):
        """n_shuffles=0 must raise ValueError."""
        with pytest.raises(ValueError, match="n_shuffles must be > 0"):
            run_shuffle_test(
                feature_df=_build_strong_signal_df(),
                flare_df=_build_flare_df(),
                thresholds=[0.5],
                n_shuffles=0,
            )

    def test_negative_shuffles_raises(self):
        """n_shuffles=-1 must raise ValueError."""
        with pytest.raises(ValueError, match="n_shuffles must be > 0"):
            run_shuffle_test(
                feature_df=_build_strong_signal_df(),
                flare_df=_build_flare_df(),
                thresholds=[0.5],
                n_shuffles=-1,
            )

    def test_one_shuffle_valid(self):
        """n_shuffles=1 is valid and returns shuffle_aucs of shape (1,)."""
        result = run_shuffle_test(
            feature_df=_build_strong_signal_df(),
            flare_df=_build_flare_df(),
            thresholds=_build_thresholds(),
            n_shuffles=1,
            random_state=30,
        )
        assert result["shuffle_aucs"].shape == (1,)
