def generate_behavior_hypotheses(trend_insights, daily_df):
    hypotheses = []

    df = daily_df.copy()

    # -------------------------
    # GLOBAL STATS (REAL SIGNALS)
    # -------------------------
    avg_glucose = df["avg_glucose"].mean()
    avg_tir = df["time_in_range"].mean()
    avg_var = df["variability"].mean()
    avg_highs = df["high_events"].mean()

    days = len(df)

    # =========================
    # 1. CHRONIC HYPERGLYCEMIA PATTERN
    # =========================
    if avg_glucose > 140:
        severity = "moderate" if avg_glucose < 160 else "high"

        hypotheses.append({
            "pattern": "Elevated baseline glucose across multiple days",
            "severity": severity,
            "confidence": 0.8 if avg_glucose > 160 else 0.6,
            "signals": [
                f"Average glucose: {avg_glucose:.1f} mg/dL across {days} days"
            ],
            "possible_causes": [
                "Consistently high carbohydrate intake",
                "Insulin resistance trend",
                "Insufficient basal coverage or long-acting insulin timing",
                "Frequent post-meal spikes without full return to baseline"
            ]
        })

    # =========================
    # 2. GLUCOSE INSTABILITY PATTERN
    # =========================
    if avg_var > 30:
        hypotheses.append({
            "pattern": "High glucose variability (unstable control)",
            "severity": "high" if avg_var > 40 else "moderate",
            "confidence": 0.75,
            "signals": [
                f"Average variability: {avg_var:.1f}"
            ],
            "possible_causes": [
                "Irregular meal timing",
                "Mixed high/low carbohydrate meals",
                "Stress-related glucose fluctuations",
                "Inconsistent insulin or medication timing",
                "Variable physical activity levels"
            ]
        })

    # =========================
    # 3. LOW TIME-IN-RANGE PATTERN
    # =========================
    if avg_tir < 70:
        hypotheses.append({
            "pattern": "Poor time-in-range control",
            "severity": "high" if avg_tir < 60 else "moderate",
            "confidence": 0.85,
            "signals": [
                f"Time in range: {avg_tir:.1f}% average"
            ],
            "possible_causes": [
                "Frequent post-meal spikes",
                "Overcorrection after highs",
                "Basal insulin mismatch",
                "Untracked carbohydrate intake",
                "Irregular daily routine"
            ]
        })

    # =========================
    # 4. SPIKE-DOMINANT PROFILE
    # =========================
    if avg_highs > 5:
        spike_ratio = avg_highs / (avg_tir + 1)

        hypotheses.append({
            "pattern": "Frequent hyperglycemic spikes",
            "severity": "high" if avg_highs > 8 else "moderate",
            "confidence": 0.7,
            "signals": [
                f"Average high events per day: {avg_highs:.1f}"
            ],
            "possible_causes": [
                "High glycemic index meals",
                "Post-meal insulin delay mismatch",
                "Snacking between meals",
                "Lack of post-meal activity (walking)",
                "Carbohydrate underestimation"
            ]
        })

    # =========================
    # 5. TREND-BASED INTELLIGENCE (FROM YOUR ENGINE)
    # =========================
    text = " ".join(trend_insights).lower()

    if "increasing over time" in text:
        hypotheses.append({
            "pattern": "Worsening metabolic trend over time",
            "severity": "high",
            "confidence": 0.9,
            "signals": [
                "Multi-day upward trend detected in glucose levels"
            ],
            "possible_causes": [
                "Progressive insulin resistance",
                "Seasonal dietary changes",
                "Reduced physical activity",
                "Sleep pattern deterioration",
                "Stress accumulation"
            ]
        })

    if "variability is increasing" in text:
        hypotheses.append({
            "pattern": "Deteriorating glucose stability over time",
            "severity": "high",
            "confidence": 0.85,
            "signals": [
                "Increasing variability across multiple days"
            ],
            "possible_causes": [
                "Inconsistent meal composition",
                "Lifestyle irregularity",
                "Changing medication effectiveness",
                "Stress or sleep disruption"
            ]
        })

    return hypotheses