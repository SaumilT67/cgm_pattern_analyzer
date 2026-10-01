import pandas as pd

def calculate_daily_metrics(df):
    """Calculate the main glucose statistics for each calendar day."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "avg_glucose",
                "time_in_range",
                "high_events",
                "low_events",
                "variability",
            ]
        )

    records = []

    data = df.copy()
    data["date"] = data["timestamp"].dt.date

    for current_date, readings in data.groupby("date"):
        glucose = readings["glucose"].dropna()

        if glucose.empty:
            continue

        total_readings = len(glucose)

        in_range_count = (
            (glucose >= 70) & (glucose <= 180)
        ).sum()

        high_count = (glucose > 180).sum()
        low_count = (glucose < 70).sum()

        range_percent = (in_range_count / total_readings) * 100
        average = glucose.mean()
        variability = glucose.std()

        records.append(
            {
                "date": current_date,
                "avg_glucose": round(average, 1),
                "time_in_range": round(range_percent, 1),
                "high_events": int(high_count),
                "low_events": int(low_count),
                "variability": round(variability, 1),
            }
        )

    return pd.DataFrame(records)
