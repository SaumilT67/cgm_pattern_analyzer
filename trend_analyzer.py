import pandas as pd

def calculate_daily_metrics(df):
    # Make a copy
    df = df.copy()

    # Extract date from timestamp
    df["date"] = df["timestamp"].dt.date

    daily_metrics = []

    for date, day_df in df.groupby("date"):

        avg_glucose = day_df["glucose"].mean()

        tir = (
            len(day_df[(day_df["glucose"] >= 70) &
                       (day_df["glucose"] <= 180)])
            / len(day_df)
        ) * 100

        highs = len(day_df[day_df["glucose"] > 180])

        lows = len(day_df[day_df["glucose"] < 70])

        variability = day_df["glucose"].std()

        daily_metrics.append({
            "date": date,
            "avg_glucose": round(avg_glucose, 1),
            "time_in_range": round(tir, 1),
            "high_events": highs,
            "low_events": lows,
            "variability": round(variability, 1)
        })

    return pd.DataFrame(daily_metrics)