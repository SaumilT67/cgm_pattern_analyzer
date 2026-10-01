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
    """Return a rounded number, or None when the value cannot be used."""
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if pd.isna(number) or not math.isfinite(number):
        return None

    return round(number, digits)



def _reading_intervals_minutes(df):
    """Estimate the minutes represented by each CGM reading."""
    timestamps = df["timestamp"]

    gaps = (
        timestamps.diff()
        .dt.total_seconds()
        .div(60)
    )

    positive_gaps = gaps[gaps > 0]

    if positive_gaps.empty:
        typical_interval = 5.0
    else:
        typical_interval = float(positive_gaps.median())

    maximum_interval = typical_interval * 2

    intervals = (
        gaps
        .fillna(typical_interval)
        .clip(lower=0, upper=maximum_interval)
    )

    return intervals, typical_interval

def _duration_in_mask(df, mask):
    """Add the estimated duration for readings selected by a boolean mask."""
    intervals, _ = _reading_intervals_minutes(df)

    selected_intervals = intervals.loc[mask]
    total_minutes = selected_intervals.sum()

    return float(total_minutes)


def calculate_daily_metrics(
    df,
    target_low=CONSENSUS_TARGET_LOW,
    target_high=CONSENSUS_TARGET_HIGH,
):
    """Build duration-weighted glucose metrics for each calendar day."""
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()
    data = data.sort_values("timestamp")
    data["date"] = data["timestamp"].dt.date

    daily_rows = []

    for current_date, day_data in data.groupby("date", sort=True):
        intervals, _ = _reading_intervals_minutes(day_data)
        total_minutes = intervals.sum()

        glucose = day_data["glucose"]

        def percentage(condition):
            if total_minutes == 0:
                return None

            matching_minutes = intervals[condition].sum()
            return _round(
                (matching_minutes / total_minutes) * 100
            )

        average = glucose.mean()
        standard_deviation = glucose.std()

        if average and not pd.isna(average):
            variation = (
                100 * standard_deviation / average
            )
        else:
            variation = None

        daily_rows.append({
            "date": str(current_date),
            "readings": int(len(day_data)),
            "average_glucose_mg_dl": _round(average),
            "glucose_sd_mg_dl": _round(standard_deviation),
            "coefficient_of_variation_percent": _round(variation),
            "time_in_range_percent": percentage(
                (glucose >= target_low) & (glucose <= target_high)
            ),
            "time_above_range_percent": percentage(
                glucose > target_high
            ),
            "time_below_range_percent": percentage(
                glucose < target_low
            ),
            "time_below_54_percent": percentage(
                glucose < 54
            ),
            "time_above_250_percent": percentage(
                glucose > 250
            ),
        })

    return pd.DataFrame(daily_rows)

def detect_glucose_episodes(df, threshold, direction="above"):
    """Group contiguous readings across a threshold into observed episodes."""
    df = df.copy().sort_values("timestamp").reset_index(drop=True)
    episodes = []
    episode_start = None
    episode_values = []

    for index, row in df.iterrows():
        glucose = row["glucose"]

        if direction == "above":
            outside = glucose > threshold
        else:
            outside = glucose < threshold

        if outside:
            if episode_start is None:
                episode_start = row["timestamp"]
                episode_values = []

            episode_values.append(glucose)
            continue

        if episode_start is not None:
            end_time = row["timestamp"]
            episode_value = (
                max(episode_values)
                if direction == "above"
                else min(episode_values)
            )

            episodes.append({
                "start": episode_start.isoformat(),
                "end": end_time.isoformat(),
                "duration_minutes": _round(
                    (end_time - episode_start).total_seconds() / 60
                ),
                "peak_glucose_mg_dl" if direction == "above" else "nadir_glucose_mg_dl": _round(episode_value),
                "reading_count": len(episode_values),
            })

            episode_start = None
            episode_values = []

    if episode_start is not None:
        end_time = df["timestamp"].iloc[-1]
        episode_value = (
            max(episode_values)
            if direction == "above"
            else min(episode_values)
        )

        episodes.append({
            "start": episode_start.isoformat(),
            "end": end_time.isoformat(),
            "duration_minutes": _round(
                (end_time - episode_start).total_seconds() / 60
            ),
            "peak_glucose_mg_dl" if direction == "above" else "nadir_glucose_mg_dl": _round(episode_value),
            "reading_count": len(episode_values),
        })

    return episodes


def analyze_data_quality(df):
    ordered = df.sort_values("timestamp")
    reading_count = len(ordered)

    first_time = ordered["timestamp"].iloc[0]
    last_time = ordered["timestamp"].iloc[-1]

    if reading_count > 1:
        elapsed_minutes = (last_time - first_time).total_seconds() / 60
    else:
        elapsed_minutes = 0

    intervals, typical_interval = _reading_intervals_minutes(ordered)

    if typical_interval:
        expected_readings = elapsed_minutes / typical_interval + 1
        coverage = min(100, 100 * reading_count / expected_readings)
    else:
        expected_readings = reading_count
        coverage = None

    gaps = ordered["timestamp"].diff().dt.total_seconds().div(60)
    large_gap_count = (gaps > typical_interval * 2).sum() if typical_interval else 0

    return {
        "reading_count": int(reading_count),
        "start": first_time.isoformat(),
        "end": last_time.isoformat(),
        "typical_sampling_interval_minutes": _round(typical_interval, 2),
        "estimated_data_coverage_percent": _round(coverage) if coverage is not None else None,
        "gaps_over_two_intervals": int(large_gap_count),
        "note": "Coverage is estimated from the typical observed sampling interval; gaps can limit interpretation.",
    }


def analyze_time_segments(df, target_low=CONSENSUS_TARGET_LOW, target_high=CONSENSUS_TARGET_HIGH):
    segments = (
        ("overnight", 0, 6),
        ("morning", 6, 12),
        ("afternoon", 12, 18),
        ("evening", 18, 24),
    )

    results = {}

    for name, start_hour, end_hour in segments:
        hours = df["timestamp"].dt.hour
        in_segment = (hours >= start_hour) & (hours < end_hour)
        part = df.loc[in_segment]

        if part.empty:
            continue

        intervals, _ = _reading_intervals_minutes(part)
        total_minutes = intervals.sum()

        in_range = (
            (part["glucose"] >= target_low)
            & (part["glucose"] <= target_high)
        )

        if total_minutes:
            time_in_range = 100 * intervals[in_range].sum() / total_minutes
        else:
            time_in_range = None

        results[name] = {
            "reading_count": int(len(part)),
            "average_glucose_mg_dl": _round(part["glucose"].mean()),
            "time_in_range_percent": _round(time_in_range) if time_in_range is not None else None,
        }

    return results


def associate_logged_meals(df, events):
    """Describe glucose observations after recorded meals without inferring meals."""
    if events is None or events.empty:
        return []

    meal_events = events[
        events["event_type"].fillna("").str.lower() == "meal"
    ]

    associations = []

    for _, meal in meal_events.iterrows():
        event_time = meal["timestamp"]

        baseline_start = event_time - pd.Timedelta(minutes=15)
        followup_end = event_time + pd.Timedelta(hours=2)

        baseline_mask = (
            (df["timestamp"] >= baseline_start)
            & (df["timestamp"] <= event_time)
        )
        followup_mask = (
            (df["timestamp"] > event_time)
            & (df["timestamp"] <= followup_end)
        )

        baseline = df.loc[baseline_mask]
        followup = df.loc[followup_mask]

        if followup.empty:
            continue

        baseline_value = (
            baseline["glucose"].mean()
            if not baseline.empty
            else None
        )
        peak_value = followup["glucose"].max()

        if baseline_value is not None:
            glucose_change = peak_value - baseline_value
        else:
            glucose_change = None

        label = meal.get("label")
        if not label:
            label = "Recorded meal"

        associations.append({
            "event_time": event_time.isoformat(),
            "event_label": label,
            "recorded_carbohydrate_grams": _round(
                meal.get("carbohydrate_grams")
            ),
            "pre_event_glucose_mg_dl": _round(baseline_value),
            "maximum_glucose_within_2h_mg_dl": _round(peak_value),
            "change_from_pre_event_mg_dl": _round(glucose_change),
            "statement": (
                "Observed after a recorded meal; this is an association, "
                "not a cause-and-effect conclusion."
            ),
        })

    return associations


def analyze_usual_meal_windows(df, usual_meal_times, target_high):
    """Summarize glucose changes around recurring scheduled meal times."""
    if not usual_meal_times:
        return []

    results = []
    dates = df["timestamp"].dt.date.dropna().unique()

    for meal_name, scheduled_time in usual_meal_times.items():
        try:
            meal_time = pd.to_datetime(scheduled_time).time()
        except (TypeError, ValueError):
            continue

        daily_changes = []
        days_above_target = 0

        for date in dates:
            scheduled_start = pd.Timestamp.combine(date, meal_time)
            baseline_start = scheduled_start - pd.Timedelta(minutes=30)
            followup_end = scheduled_start + pd.Timedelta(hours=2)

            baseline_mask = (
                (df["timestamp"] >= baseline_start)
                & (df["timestamp"] <= scheduled_start)
            )
            followup_mask = (
                (df["timestamp"] > scheduled_start)
                & (df["timestamp"] <= followup_end)
            )

            baseline = df.loc[baseline_mask]
            followup = df.loc[followup_mask]

            if baseline.empty or followup.empty:
                continue

            baseline_value = baseline["glucose"].mean()
            peak_value = followup["glucose"].max()

            daily_changes.append(peak_value - baseline_value)

            if peak_value > target_high:
                days_above_target += 1

        if not daily_changes:
            continue

        results.append({
            "meal_name": meal_name.title(),
            "usual_time": scheduled_time,
            "days_with_enough_data": len(daily_changes),
            "average_peak_change_mg_dl": _round(np.mean(daily_changes)),
            "days_with_value_above_target_in_next_2h": days_above_target,
            "statement": (
                "This compares readings near a usual scheduled time. "
                "It does not confirm that a meal occurred or that it caused "
                "a glucose change."
            ),
        })

    return results


def build_clinical_evidence_report(
    df,
    target_low,
    target_high,
    events=None,
    patient_context=None,
):
    """Build a JSON-serializable report for clinician or AI review."""
    if df.empty:
        raise ValueError("No valid CGM readings were found.")

    source_summary = df.attrs.get("source_summary", {})
    daily_metrics = calculate_daily_metrics(df, target_low, target_high)

    intervals, _ = _reading_intervals_minutes(df)
    total_minutes = intervals.sum()

    def percentage(mask):
        if not total_minutes:
            return None
        return _round(100 * intervals[mask].sum() / total_minutes)

    above_target = detect_glucose_episodes(
        df,
        target_high,
        "above",
    )
    below_target = detect_glucose_episodes(
        df,
        target_low,
        "below",
    )

    recorded_events = associate_logged_meals(df, events)

    context = patient_context or {}
    meal_schedule = context.get("usual_meal_times", {})
    usual_meal_times = meal_schedule.get("times", {})

    scheduled_meal_observations = analyze_usual_meal_windows(
        df,
        usual_meal_times,
        target_high,
    )

    if events is None or events.empty:
        limitations = [
            "No meal or event log was added, so this summary cannot tell what happened around a glucose change.",
            "Glucose readings alone cannot show why a pattern happened or determine a treatment change.",
        ]
    else:
        limitations = [
            "Only the events that were added were reviewed. Other meals, medicine, activity, illness, stress, sleep, and sensor issues may be unknown."
        ]

    review_questions = [
        "What was known around these times—such as meals, medicine, activity, illness, stress, sleep, or symptoms? Add only information that is known.",
        "Is the selected glucose range the one agreed with the care team?",
    ]

    if not recorded_events:
        review_questions.append(
            "Would a time-stamped meal or event log be useful next time? Without one, this report cannot link a change to a meal."
        )

    glucose_mean = df["glucose"].mean()
    glucose_sd = df["glucose"].std()

    measured_metrics = {
        "average_glucose_mg_dl": _round(glucose_mean),
        "glucose_sd_mg_dl": _round(glucose_sd),
        "coefficient_of_variation_percent": _round(
            100 * glucose_sd / glucose_mean
        ),
        "time_in_range_percent": percentage(
            (df["glucose"] >= target_low)
            & (df["glucose"] <= target_high)
        ),
        "time_above_range_percent": percentage(
            df["glucose"] > target_high
        ),
        "time_below_range_percent": percentage(
            df["glucose"] < target_low
        ),
        "time_below_54_percent": percentage(
            df["glucose"] < 54
        ),
        "time_above_250_percent": percentage(
            df["glucose"] > 250
        ),
    }

    return {
        "report_version": "1.0",
        "purpose": (
            "Clinical decision-support summary; not a diagnosis "
            "or treatment recommendation."
        ),
        "patient_context": context,
        "target_range_mg_dl": {
            "lower": target_low,
            "upper": target_high,
            "source": "user-entered; verify with treating clinician",
        },
        "source_data": source_summary,
        "data_quality": analyze_data_quality(df),
        "measured_metrics": measured_metrics,
        "daily_metrics": daily_metrics.to_dict(orient="records"),
        "time_of_day_observations": analyze_time_segments(
            df,
            target_low,
            target_high,
        ),
        "observed_episodes": {
            "above_target": above_target,
            "below_target": below_target,
        },
        "recorded_event_associations": recorded_events,
        "usual_meal_time_observations": scheduled_meal_observations,
        "questions_for_clinical_review": review_questions,
        "limitations": limitations,
        "safety_notice": (
            "Escalate urgent symptoms or concerning low/high glucose "
            "readings according to the patient's existing care plan and "
            "local emergency guidance. This software must not direct "
            "medication changes."
        ),
    }


# Compatibility wrappers retained for existing callers.
def detect_patterns(df):
    """Return the legacy pattern summary used by older callers."""
    report = build_clinical_evidence_report(
        df,
        CONSENSUS_TARGET_LOW,
        CONSENSUS_TARGET_HIGH,
    )

    metrics = report["measured_metrics"]
    time_in_range = metrics["time_in_range_percent"]

    return [f"Time in range: {time_in_range}%"]

def analyze_trends(daily_df):
    """Keep the legacy trend interface available until trend analysis is expanded."""
    if daily_df is None:
        return []

    return []


def build_glucose_behavior_model(df):
    """Keep the legacy interface while directing callers to the current report."""
    status = "Deprecated: use build_clinical_evidence_report()."
    return {"status": status}


def detect_spike_events(df, threshold=180):
    """Return observed glucose episodes above the requested threshold."""
    episodes = detect_glucose_episodes(
        df,
        threshold=threshold,
        direction="above",
    )

    return episodes


def analyze_recovery_behavior(df, spikes, recovery_threshold=140):
    """Keep recovery analysis disabled without documented clinical context."""
    status = "Not reported without documented clinical context."

    return {
        "status": status,
    }
