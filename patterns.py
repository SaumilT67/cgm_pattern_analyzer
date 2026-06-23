import pandas as pd

def detect_patterns(df):
    insights = []

    # -------------------------
    # TIME IN RANGE
    # -------------------------
    in_range = df[(df["glucose"] >= 70) & (df["glucose"] <= 180)]
    tir = len(in_range) / len(df) * 100
    insights.append(f"Time in Range: {tir:.1f}%")

    # -------------------------
    # HYPERGLYCEMIA
    # -------------------------
    highs = df[df["glucose"] > 180]
    insights.append(f"High glucose events: {len(highs)}")

    # -------------------------
    # HYPOGLYCEMIA
    # -------------------------
    lows = df[df["glucose"] < 70]
    insights.append(f"Low glucose events: {len(lows)}")

    # -------------------------
    # SEVERE EVENTS (NEW IMPORTANT SIGNAL)
    # -------------------------
    severe_highs = df[df["glucose"] > 250]
    severe_lows = df[df["glucose"] < 54]

    insights.append(f"Severe highs (>250): {len(severe_highs)}")
    insights.append(f"Severe lows (<54): {len(severe_lows)}")

    # -------------------------
    # VARIABILITY (CRITICAL METRIC)
    # -------------------------
    variability = df["glucose"].std()
    insights.append(f"Glucose variability (std dev): {variability:.1f}")

    # -------------------------
    # TREND ANALYSIS
    # -------------------------
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