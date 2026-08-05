"""Evidence-first CGM analysis.

This module intentionally reports observations, not diagnoses or treatment advice.
Clinical interpretation requires the patient, their documented context, and a qualified
health-care professional.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


CONSENSUS_TARGET_LOW = 70
CONSENSUS_TARGET_HIGH = 180


def _round(value, digits=1):
    """Round finite numeric values while preserving missing values as None."""
    if value is None or pd.isna(value) or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _reading_intervals_minutes(df):
    """Return the duration represented by each reading, capped at 2x typical interval."""
    deltas = df["timestamp"].diff().dt.total_seconds().div(60)
    typical = deltas[deltas > 0].median()
    if pd.isna(typical):
        typical = 5.0
    return deltas.fillna(typical).clip(lower=0, upper=typical * 2), float(typical)


def _duration_in_mask(df, mask):
    intervals, _ = _reading_intervals_minutes(df)
    return float(intervals[mask].sum())


def calculate_daily_metrics(df, target_low=CONSENSUS_TARGET_LOW, target_high=CONSENSUS_TARGET_HIGH):
    """Calculate duration-weighted daily CGM metrics for a patient-selected target range."""
    df = df.copy().sort_values("timestamp")
    df["date"] = df["timestamp"].dt.date
    rows = []
    for date, day in df.groupby("date", sort=True):
        intervals, _ = _reading_intervals_minutes(day)
        total_minutes = intervals.sum()
        def percent(mask):
            return _round(100 * intervals[mask].sum() / total_minutes) if total_minutes else None
        rows.append({
            "date": str(date),
            "readings": int(len(day)),
            "average_glucose_mg_dl": _round(day["glucose"].mean()),
            "glucose_sd_mg_dl": _round(day["glucose"].std()),
            "coefficient_of_variation_percent": _round(100 * day["glucose"].std() / day["glucose"].mean()),
            "time_in_range_percent": percent((day.glucose >= target_low) & (day.glucose <= target_high)),
            "time_above_range_percent": percent(day.glucose > target_high),
            "time_below_range_percent": percent(day.glucose < target_low),
            "time_below_54_percent": percent(day.glucose < 54),
            "time_above_250_percent": percent(day.glucose > 250),
        })
    return pd.DataFrame(rows)


def detect_glucose_episodes(df, threshold, direction="above"):
    """Group contiguous readings across a threshold into observed episodes."""
    df = df.copy().sort_values("timestamp").reset_index(drop=True)
    is_outside = df.glucose > threshold if direction == "above" else df.glucose < threshold
    episodes, start = [], None
    for i, outside in enumerate(is_outside):
        if outside and start is None:
            start = i
        if start is not None and (not outside or i == len(df) - 1):
            end = i if outside and i == len(df) - 1 else i - 1
            next_time = df.loc[i, "timestamp"] if not outside else df.loc[end, "timestamp"]
            segment = df.iloc[start:end + 1]
            episodes.append({
                "start": segment.timestamp.iloc[0].isoformat(),
                "end": next_time.isoformat(),
                "duration_minutes": _round((next_time - segment.timestamp.iloc[0]).total_seconds() / 60),
                "peak_glucose_mg_dl" if direction == "above" else "nadir_glucose_mg_dl": _round(segment.glucose.max() if direction == "above" else segment.glucose.min()),
                "reading_count": int(len(segment)),
            })
            start = None
    return episodes


def analyze_data_quality(df):
    df = df.sort_values("timestamp")
    intervals, typical = _reading_intervals_minutes(df)
    elapsed = (df.timestamp.iloc[-1] - df.timestamp.iloc[0]).total_seconds() / 60 if len(df) > 1 else 0
    expected = (elapsed / typical + 1) if typical else len(df)
    gaps = df.timestamp.diff().dt.total_seconds().div(60)
    return {
        "reading_count": int(len(df)),
        "start": df.timestamp.iloc[0].isoformat(),
        "end": df.timestamp.iloc[-1].isoformat(),
        "typical_sampling_interval_minutes": _round(typical, 2),
        "estimated_data_coverage_percent": _round(min(100, 100 * len(df) / expected)) if expected else None,
        "gaps_over_two_intervals": int((gaps > typical * 2).sum()),
        "note": "Coverage is estimated from the typical observed sampling interval; gaps can limit interpretation.",
    }


def analyze_time_segments(df, target_low=CONSENSUS_TARGET_LOW, target_high=CONSENSUS_TARGET_HIGH):
    df = df.copy()
    df["hour"] = df.timestamp.dt.hour
    segments = {"overnight": (0, 6), "morning": (6, 12), "afternoon": (12, 18), "evening": (18, 24)}
    results = {}
    for name, (start, end) in segments.items():
        part = df[(df.hour >= start) & (df.hour < end)]
        if len(part):
            intervals, _ = _reading_intervals_minutes(part)
            total = intervals.sum()
            results[name] = {
                "reading_count": int(len(part)),
                "average_glucose_mg_dl": _round(part.glucose.mean()),
                "time_in_range_percent": _round(100 * intervals[(part.glucose >= target_low) & (part.glucose <= target_high)].sum() / total) if total else None,
            }
    return results


def associate_logged_meals(df, events):
    """Describe glucose observations after *recorded* meals; never infer unrecorded meals."""
    if events is None or events.empty:
        return []
    meals = events[events["event_type"].str.lower().eq("meal")]
    associations = []
    for _, meal in meals.iterrows():
        event_time = meal.timestamp
        baseline = df[(df.timestamp >= event_time - pd.Timedelta(minutes=15)) & (df.timestamp <= event_time)]
        followup = df[(df.timestamp > event_time) & (df.timestamp <= event_time + pd.Timedelta(hours=2))]
        if followup.empty:
            continue
        baseline_value = baseline.glucose.mean() if not baseline.empty else None
        peak = followup.glucose.max()
        associations.append({
            "event_time": event_time.isoformat(),
            "event_label": meal.get("label") or "Recorded meal",
            "recorded_carbohydrate_grams": _round(meal.get("carbohydrate_grams")),
            "pre_event_glucose_mg_dl": _round(baseline_value),
            "maximum_glucose_within_2h_mg_dl": _round(peak),
            "change_from_pre_event_mg_dl": _round(peak - baseline_value) if baseline_value is not None else None,
            "statement": "Observed after a recorded meal; this is an association, not a cause-and-effect conclusion.",
        })
    return associations


def analyze_usual_meal_windows(df, usual_meal_times, target_high):
    """Measure repeated glucose changes near a *general* meal schedule.

    A schedule is not a meal log. These results therefore describe timing only and
    are deliberately not labelled as post-meal responses.
    """
    if not usual_meal_times:
        return []
    results = []
    dates = pd.Series(df.timestamp.dt.date.unique()).dropna()
    for meal, value in usual_meal_times.items():
        try:
            meal_time = pd.to_datetime(value).time()
        except (TypeError, ValueError):
            continue
        changes, high_window_days = [], 0
        for date in dates:
            window_start = pd.Timestamp.combine(date, meal_time)
            before = df[(df.timestamp >= window_start - pd.Timedelta(minutes=30)) & (df.timestamp <= window_start)]
            after = df[(df.timestamp > window_start) & (df.timestamp <= window_start + pd.Timedelta(hours=2))]
            if before.empty or after.empty:
                continue
            baseline = before.glucose.mean()
            peak = after.glucose.max()
            changes.append(peak - baseline)
            if peak > target_high:
                high_window_days += 1
        if changes:
            results.append({
                "meal_name": meal.title(),
                "usual_time": value,
                "days_with_enough_data": len(changes),
                "average_peak_change_mg_dl": _round(np.mean(changes)),
                "days_with_value_above_target_in_next_2h": high_window_days,
                "statement": "This compares readings near a usual scheduled time. It does not confirm that a meal occurred or that it caused a glucose change.",
            })
    return results


def build_clinical_evidence_report(df, target_low, target_high, events=None, patient_context=None):
    """Build a JSON-serializable report suitable for review by a clinician or AI."""
    if df.empty:
        raise ValueError("No valid CGM readings were found.")
    source_summary = df.attrs.get("source_summary", {})
    daily = calculate_daily_metrics(df, target_low, target_high)
    intervals, _ = _reading_intervals_minutes(df)
    total = intervals.sum()
    def pct(mask):
        return _round(100 * intervals[mask].sum() / total) if total else None
    high = detect_glucose_episodes(df, target_high, "above")
    low = detect_glucose_episodes(df, target_low, "below")
    meal_associations = associate_logged_meals(df, events)
    usual_meal_times = (patient_context or {}).get("usual_meal_times", {}).get("times", {})
    usual_meal_observations = analyze_usual_meal_windows(df, usual_meal_times, target_high)
    missing_context = [
        "No meal or event log was added, so this summary cannot tell what happened around a glucose change.",
        "Glucose readings alone cannot show why a pattern happened or determine a treatment change.",
    ]
    if events is not None and not events.empty:
        missing_context = ["Only the events that were added were reviewed. Other meals, medicine, activity, illness, stress, sleep, and sensor issues may be unknown."]
    review_questions = [
        "What was known around these times—such as meals, medicine, activity, illness, stress, sleep, or symptoms? Add only information that is known.",
        "Is the selected glucose range the one agreed with the care team?",
    ]
    if not meal_associations:
        review_questions.append("Would a time-stamped meal or event log be useful next time? Without one, this report cannot link a change to a meal.")
    return {
        "report_version": "1.0",
        "purpose": "Clinical decision-support summary; not a diagnosis or treatment recommendation.",
        "patient_context": patient_context or {},
        "target_range_mg_dl": {"lower": target_low, "upper": target_high, "source": "user-entered; verify with treating clinician"},
        "source_data": source_summary,
        "data_quality": analyze_data_quality(df),
        "measured_metrics": {
            "average_glucose_mg_dl": _round(df.glucose.mean()),
            "glucose_sd_mg_dl": _round(df.glucose.std()),
            "coefficient_of_variation_percent": _round(100 * df.glucose.std() / df.glucose.mean()),
            "time_in_range_percent": pct((df.glucose >= target_low) & (df.glucose <= target_high)),
            "time_above_range_percent": pct(df.glucose > target_high),
            "time_below_range_percent": pct(df.glucose < target_low),
            "time_below_54_percent": pct(df.glucose < 54),
            "time_above_250_percent": pct(df.glucose > 250),
        },
        "daily_metrics": daily.to_dict(orient="records"),
        "time_of_day_observations": analyze_time_segments(df, target_low, target_high),
        "observed_episodes": {"above_target": high, "below_target": low},
        "recorded_event_associations": meal_associations,
        "usual_meal_time_observations": usual_meal_observations,
        "questions_for_clinical_review": review_questions,
        "limitations": missing_context,
        "safety_notice": "Escalate urgent symptoms or concerning low/high glucose readings according to the patient's existing care plan and local emergency guidance. This software must not direct medication changes.",
    }


# Compatibility wrappers retained for existing callers.
def detect_patterns(df):
    report = build_clinical_evidence_report(df, CONSENSUS_TARGET_LOW, CONSENSUS_TARGET_HIGH)
    return [f"Time in range: {report['measured_metrics']['time_in_range_percent']}%"]


def analyze_trends(daily_df):
    return []


def build_glucose_behavior_model(df):
    return {"status": "Deprecated: use build_clinical_evidence_report()."}


def detect_spike_events(df, threshold=180):
    return detect_glucose_episodes(df, threshold, "above")


def analyze_recovery_behavior(df, spikes, recovery_threshold=140):
    return {"status": "Not reported without documented clinical context."}
