import pandas as pd


def calculate_daily_metrics(df):
    df = df.copy()
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


def analyze_trends(daily_df):
    insights = []
    daily_df = daily_df.sort_values("date")

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

    tir_change = daily_df["time_in_range"].iloc[-1] - daily_df["time_in_range"].iloc[0]
    if tir_change < -5:
        insights.append("Time in range is decreasing")
    elif tir_change > 5:
        insights.append("Time in range is improving")

    if "variability" in daily_df.columns:
        var_change = daily_df["variability"].iloc[-1] - daily_df["variability"].iloc[0]
        if var_change > 5:
            insights.append("Glucose variability is increasing (less stable control)")
        elif var_change < -5:
            insights.append("Glucose variability is decreasing (more stable control)")

    if "high_events" in daily_df.columns:
        spike_change = daily_df["high_events"].iloc[-1] - daily_df["high_events"].iloc[0]
        if spike_change > 0:
            insights.append("High glucose events are becoming more frequent")
        elif spike_change < 0:
            insights.append("High glucose events are decreasing")

    return insights


def detect_patterns(df):
    insights = []

    in_range = df[(df["glucose"] >= 70) & (df["glucose"] <= 180)]
    tir = len(in_range) / len(df) * 100
    insights.append(f"Time in Range: {tir:.1f}%")

    highs = df[df["glucose"] > 180]
    insights.append(f"High glucose events: {len(highs)}")

    lows = df[df["glucose"] < 70]
    insights.append(f"Low glucose events: {len(lows)}")

    severe_highs = df[df["glucose"] > 250]
    severe_lows = df[df["glucose"] < 54]
    insights.append(f"Severe highs (>250): {len(severe_highs)}")
    insights.append(f"Severe lows (<54): {len(severe_lows)}")

    variability = df["glucose"].std()
    insights.append(f"Glucose variability (std dev): {variability:.1f}")

    df = df.copy()
    df["hour"] = df["timestamp"].dt.hour

    morning = df[(df["hour"] >= 6) & (df["hour"] <= 10)]["glucose"]
    night = df[(df["hour"] >= 22) | (df["hour"] <= 4)]["glucose"]

    if len(morning) > 5 and len(night) > 5:
        morning_avg = morning.mean()
        night_avg = night.mean()

        if morning_avg > night_avg:
            insights.append("Morning glucose is higher than night (possible dawn phenomenon)")
        else:
            insights.append("Night glucose is higher than morning")

    return insights


def build_glucose_behavior_model(df):
    df = df.copy()

    df["hour"] = df["timestamp"].dt.hour

    model = {}

    # ----------------------------
    # 1. Overnight behavior
    # ----------------------------
    overnight = df[(df["hour"] <= 5)]
    model["overnight_mean"] = round(overnight["glucose"].mean(), 1)
    model["overnight_std"] = round(overnight["glucose"].std(), 1)

    # ----------------------------
    # 2. Dawn phenomenon detection
    # ----------------------------
    early_morning = df[(df["hour"] >= 5) & (df["hour"] <= 9)]

    model["morning_rise"] = None
    if len(overnight) > 10 and len(early_morning) > 10:
        model["morning_rise"] = round(
            early_morning["glucose"].mean() - overnight["glucose"].mean(),
            1
        )

    # ----------------------------
    # 3. Spike classification
    # ----------------------------
    spikes = df[df["glucose"] > 180]

    model["spike_rate"] = round(len(spikes) / len(df) * 100, 2)

    severe = df[df["glucose"] > 250]
    extreme = df[df["glucose"] > 300]

    model["spike_severity_profile"] = {
        "180_250": len(spikes) - len(severe),
        "250_300": len(severe) - len(extreme),
        "300_plus": len(extreme)
    }

    # ----------------------------
    # 4. Volatility regimes
    # ----------------------------
    df["rolling_std"] = df["glucose"].rolling(12).std()

    model["avg_volatility"] = round(df["rolling_std"].mean(), 1)

    # ----------------------------
    # 5. Recovery behavior
    # ----------------------------
    recovery_times = []

    for i in range(len(df) - 1):
        if df.iloc[i]["glucose"] > 180:
            for j in range(i, min(i + 24, len(df))):
                if df.iloc[j]["glucose"] < 140:
                    recovery_times.append(j - i)
                    break

    model["avg_recovery_time"] = round(sum(recovery_times) / len(recovery_times), 1) if recovery_times else None

    # ----------------------------
    # 6. Stability classification
    # ----------------------------
    cv = df["glucose"].std() / df["glucose"].mean()
    model["coefficient_variation"] = round(cv, 3)

    if cv < 0.15:
        model["stability_class"] = "stable"
    elif cv < 0.25:
        model["stability_class"] = "moderate"
    else:
        model["stability_class"] = "unstable"

    return model