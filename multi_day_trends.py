import pandas as pd

def analyze_trends(daily_df):
    insights = []

    daily_df = daily_df.sort_values("date")

    # -------------------------
    # TREND: AVG GLUCOSE OVER TIME
    # -------------------------
    if len(daily_df) >= 3:
        start = daily_df["avg_glucose"].iloc[0]
        end = daily_df["avg_glucose"].iloc[-1]

        change = end - start

        if change > 10:
            insights.append("Average glucose is increasing over time")
        elif change < -10:
            insights.append("Average glucose is improving over time")
        else:
            insights.append("Average glucose is stable over time")

    # -------------------------
    # TREND: TIME IN RANGE
    # -------------------------
    tir_change = daily_df["time_in_range"].iloc[-1] - daily_df["time_in_range"].iloc[0]

    if tir_change < -5:
        insights.append("Time in range is decreasing")
    elif tir_change > 5:
        insights.append("Time in range is improving")

    # -------------------------
    # VARIABILITY TREND
    # -------------------------
    if "variability" in daily_df.columns:
        var_change = daily_df["variability"].iloc[-1] - daily_df["variability"].iloc[0]

        if var_change > 5:
            insights.append("Glucose variability is increasing (less stable control)")
        elif var_change < -5:
            insights.append("Glucose variability is decreasing (more stable control)")

    # -------------------------
    # SPIKE TREND
    # -------------------------
    if "high_events" in daily_df.columns:
        spike_change = daily_df["high_events"].iloc[-1] - daily_df["high_events"].iloc[0]

        if spike_change > 0:
            insights.append("High glucose events are becoming more frequent")
        elif spike_change < 0:
            insights.append("High glucose events are decreasing")

    return insights