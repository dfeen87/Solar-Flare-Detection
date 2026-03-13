# Analysis and Validation of Precursor Signals

## 1. Overview

This document describes the methodology used to evaluate precursor signals
derived from solar-flare observational data.  The primary precursor under
investigation is ΔΦ(t), a phase-difference quantity computed from magnetic
and X-ray measurements recorded by the GOES satellite constellation.  The
evaluation pipeline assesses whether ΔΦ(t) and composite features derived
from it carry measurable predictive information about imminent solar-flare
events at timescales ranging from minutes to hours ahead of onset.

The pipeline consists of four stages: data ingestion and alignment, precursor
construction, event-based evaluation, and statistical falsification via a
shuffle test.  Each stage is described in the sections that follow.  The goal
is to produce results that are reproducible, statistically defensible, and
suitable for inclusion in a peer-reviewed manuscript.

---

## 2. Data Sources

All input data are sourced from the NOAA Geostationary Operational
Environmental Satellite (GOES) archive.

**GOES X-ray flux** records broad-band solar soft X-ray irradiance in the 1–8 Å
channel at one-minute cadence.  This channel is the standard reference for
classifying solar flares by peak flux (A, B, C, M, X classes).

**GOES EUVS (Extreme Ultraviolet Sensor)** provides irradiance in the
extreme-ultraviolet band, complementing the X-ray flux data and offering an
additional energetic channel for composite feature construction.

**GOES magnetometer** data supply the solar wind magnetic field components used
in the computation of the phase quantity Φ(t).  Cadence and channel selection
follow published GOES Level 2 data product specifications.

**Flare catalogue** entries are drawn from the GOES flare event list, which
records onset time, peak time, end time, and peak flux class for each
confirmed solar flare.  Only the onset time is used in the evaluation pipeline;
peak and end times are retained for reference but are not used in any metric
computation.

All timestamps are treated as UTC throughout the pipeline.  No timezone
conversions are applied after ingestion.  Missing data are represented as
IEEE 754 NaN values and are excluded from computation at each processing step.

---

## 3. Precursor Construction

**ΔΦ(t)** is defined as the rate of change of the phase angle Φ(t) derived from
the GOES magnetometer components.  It is computed at each cadence step using a
finite-difference approximation and serves as the primary scalar precursor
signal.  The construction avoids interpolation: whenever a cadence step is
missing, the corresponding ΔΦ value is left as NaN and dropped from subsequent
analysis.

**Composite features** extend the scalar ΔΦ signal by combining multiple derived
quantities (e.g., smoothed derivatives, band-limited energy proxies, running
standard deviations) into a single feature table.  The feature table is
constructed using an outer join on the common UTC timestamp index, so that no
artificial imputation is introduced.  Each column in the feature table
represents one candidate precursor variable and can be evaluated independently
or in combination.

The feature table is the direct input to the evaluation pipeline.  Users
select a specific column as the active signal via the `value_col` parameter.
The default column is `delta_phi`.

---

## 4. Evaluation Method

Precursor performance is assessed using an event-based evaluation framework
that respects the asymmetry between flare and non-flare time periods.

For each flare in the catalogue a **pre-flare window** is defined as the
interval ending at the flare onset time and extending backwards by a fixed
look-ahead duration.  Signal values that fall within this window are treated
as positive instances; all other signal values are treated as negative
instances.

**Threshold sweep**: a series of detection thresholds is applied to the signal.
At each threshold the evaluation counts true positives (flare windows in which
the signal exceeds the threshold), false positives (non-flare intervals in
which the signal exceeds the threshold), true negatives, and false negatives.
From these counts standard metrics including sensitivity (TPR), specificity,
and false-positive rate (FPR) are derived.

**Lead-time analysis**: for each flare the evaluation records the time from the
first threshold crossing to the flare onset (first-crossing lead time) and the
time from the signal maximum to onset (max-signal lead time).  These quantities
characterise how far in advance the precursor becomes detectable.

**ROC curve and AUC**: the threshold sweep over the full range of values
generates a receiver-operating-characteristic curve.  The area under this curve
(AUC) summarises classification performance as a single scalar, with 0.5
representing chance-level performance and 1.0 representing perfect
classification.  AUC values are computed via the trapezoidal rule.

---

## 5. Shuffle Test (Null Model)

The shuffle test provides statistical evidence that a measured AUC exceeds
what would be expected under a null hypothesis of no temporal structure in the
precursor signal.

The procedure is as follows.  Given the real precursor signal with timestamps
tᵢ and values S(tᵢ), a set of n_shuffles permuted signals is generated.  In
each permutation the values S(tᵢ) are randomly re-assigned to the same set of
timestamps, preserving the marginal distribution of signal values while
destroying any temporal order.  The evaluation pipeline is then applied to
each permuted signal, and the resulting AUC is recorded.  This produces a null
distribution of AUC values representing performance under the assumption that
the precursor carries no causal temporal information.

The default number of shuffles is 200, which provides a null distribution with
sufficient resolution to detect p-values as small as 0.005.  The shuffles are
generated using a seeded pseudorandom number generator (NumPy's PCG-64 via
`numpy.random.default_rng`) so that results are fully reproducible when a
`random_state` seed is provided.

NaN values in the signal are dropped before shuffling so that the permutation
is performed only on valid observations.  The timestamps of valid observations
are preserved exactly; no interpolation or gap-filling is applied.

---

## 6. Results Structure

The shuffle test returns a dictionary with three fields.

**`real_auc`** (float): the AUC of the unshuffled precursor signal computed by
the standard evaluation pipeline over the full threshold sweep.

**`shuffle_aucs`** (numpy.ndarray, shape `(n_shuffles,)`): the AUC values
obtained from each of the n_shuffles random permutations.  This array
constitutes the empirical null distribution.

**`p_value`** (float): the fraction of shuffled AUC values that are greater
than or equal to the real AUC.  Formally:

    p = #{shuffle_aucs ≥ real_auc} / n_shuffles

A p-value of 0.0 indicates that none of the shuffled signals achieved an AUC
as high as the real precursor.  A p-value of 1.0 indicates that all shuffled
signals performed at least as well as the real precursor.

---

## 7. Interpretation

A p-value below a chosen significance threshold (conventionally 0.05)
constitutes evidence against the null hypothesis that the precursor carries no
temporal information about flare onset.  Under this interpretation a small
p-value suggests that the observed AUC is unlikely to arise by chance and that
the precursor signal contains genuine predictive structure.

Conversely, a large p-value (e.g. p > 0.1) indicates that the precursor
performs no better than a randomly ordered signal at the same threshold
settings and over the same evaluation period.  In this case the precursor
cannot be considered statistically validated for the data period under study.

The magnitude of the AUC difference between the real signal and the median of
the null distribution quantifies the practical effect size.  A statistically
significant but numerically small AUC difference may have limited operational
value even if the p-value is low.  Both the p-value and the AUC difference
should therefore be reported and interpreted together.

It is important to note that the shuffle test as implemented is marginal with
respect to the threshold set: the same threshold array is used for both the
real and shuffled evaluations.  Selecting thresholds post hoc based on
inspection of the real signal would inflate the apparent AUC and invalidate the
p-value; thresholds should therefore be chosen a priori or on a held-out
validation period.

---

## 8. Conclusion

The evaluation pipeline described in this document provides a principled,
reproducible framework for assessing whether ΔΦ(t) and composite solar-flare
precursor signals carry measurable predictive information above the level
expected by chance.

The combination of event-based evaluation (lead times, ROC, AUC) and the
shuffle-test null model yields both practical and statistical characterisation
of precursor quality.  A precursor that achieves a high AUC with a
statistically significant p-value under the shuffle test provides empirical
evidence of genuine predictive structure in the signal, motivating further
physical investigation and operational development.

Precursors that fail to surpass the null model should not be advanced to
downstream modelling stages without additional refinement or re-evaluation on
independent data.  The pipeline is designed to make this gate transparent and
computationally reproducible for any candidate signal that can be expressed as
a time-indexed scalar column in a pandas DataFrame.

---

## 9. Reproducible Evaluation Intervals

Three standard evaluation intervals are provided for manuscript analysis:

- **1 month** — covers the 30-day period immediately preceding the run date.
- **6 months** — covers the 182-day period immediately preceding the run date.
- **1 year** — covers the 365-day period immediately preceding the run date.

Each interval is executed via a dedicated script in the `experiments/`
directory and produces structured JSON results in `results/`.  These intervals
correspond to the ranges used in the paper and allow exact regeneration of all
reported metrics and shuffle-test statistics.

### Scripts

| Script | Interval | Output |
|--------|----------|--------|
| `experiments/eval_one_month.py` | 1 month (30 days) | `results/eval_one_month.json` |
| `experiments/eval_six_months.py` | 6 months (182 days) | `results/eval_six_months.json` |
| `experiments/eval_one_year.py` | 1 year (365 days) | `results/eval_one_year.json` |

All three wrappers delegate to `experiments/run_interval_eval.py`, which
accepts arbitrary `--start` / `--end` date arguments and supports optional
`--value-col`, `--n-shuffles`, `--random-state`, and `--output` flags for
full parametric control.

### Example

```bash
python experiments/eval_one_month.py --n-shuffles 500 --random-state 0
```

or equivalently:

```bash
python experiments/run_interval_eval.py \
    --start 2024-01-01 \
    --end   2024-02-01 \
    --value-col delta_phi \
    --n-shuffles 500 \
    --random-state 0 \
    --output results/eval_2024-01-01_to_2024-02-01.json
```

### Output schema

Each JSON artifact produced by the scripts follows this schema:

```json
{
  "interval": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "value_col": "<feature_name>",
  "real_auc": 0.73,
  "shuffle_aucs": [0.51, 0.49, ...],
  "p_value": 0.02,
  "lead_times": [...],
  "threshold_metrics": [...],
  "roc": {"fpr": [...], "tpr": [...], "thresholds": [...]}
}
```

All timestamps are ISO-8601 UTC strings; NaN values are serialised as `null`.
The `results/` directory is excluded from version control (see `.gitignore`)
except for the `results/.keep` placeholder.  Re-running any wrapper script
regenerates the corresponding artifact deterministically when `--random-state`
is fixed.
