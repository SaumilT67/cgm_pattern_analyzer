def generate_behavior_hypotheses(trend_insights, daily_df):

    hypotheses = []

    df = daily_df.copy()

    avg_glucose = df["avg_glucose"].mean()
    avg_tir = df["time_in_range"].mean()
    avg_var = df["variability"].mean()
    avg_highs = df["high_events"].mean()

    # -------------------------
    # HIGH GLUCOSE BASELINE
    # -------------------------
    if avg_glucose > 140:
        hypotheses.append({
            "pattern": "Elevated baseline glucose across multiple days",
            "confidence": 0.7,
            "signals": [f"Avg glucose {avg_glucose:.1f}"],
            "possible_causes": [
                "Consistent high carbohydrate intake",
                "Insulin resistance trend",
                "Basal insulin mismatch"
            ]
        })

    # -------------------------
    # VARIABILITY
    # -------------------------
    if avg_var > 30:
        hypotheses.append({
            "pattern": "High glucose variability",
            "confidence": 0.75,
            "signals": [f"Variability {avg_var:.1f}"],
            "possible_causes": [
                "Irregular meal timing",
                "Stress / sleep disruption",
                "Mixed meal composition"
            ]
        })

    # -------------------------
    # LOW TIME IN RANGE
    # -------------------------
    if avg_tir < 70:
        hypotheses.append({
            "pattern": "Poor time in range",
            "confidence": 0.8,
            "signals": [f"TIR {avg_tir:.1f}%"],
            "possible_causes": [
                "Frequent post-meal spikes",
                "Insulin timing mismatch",
                "Diet inconsistency"
            ]
        })

    # -------------------------
    # SPIKE FREQUENCY
    # -------------------------
    if avg_highs > 5:
        hypotheses.append({
            "pattern": "Frequent glucose spikes",
            "confidence": 0.7,
            "signals": [f"{avg_highs:.1f} highs/day"],
            "possible_causes": [
                "High glycemic meals",
                "Late eating",
                "Snacking patterns"
            ]
        })

    return hypotheses


def generate_questions(hypotheses):

    questions = []

    for h in hypotheses:

        p = h["pattern"].lower()

        if "baseline" in p:
            questions.append(
                "Do you notice higher glucose on days with similar meal timing or composition?"
            )

        if "variability" in p:
            questions.append(
                "Do your glucose levels change more on days with irregular meals or sleep?"
            )

        if "time in range" in p:
            questions.append(
                "Which meals or times of day most often push you out of range?"
            )

        if "spikes" in p:
            questions.append(
                "Do spikes usually occur after specific meals or at consistent times?"
            )

    return list(dict.fromkeys(questions))