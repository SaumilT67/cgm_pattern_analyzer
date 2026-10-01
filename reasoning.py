def generate_behavior_hypotheses(trend_insights, daily_df):
    """Turn observed trends into cautious, non-diagnostic hypotheses."""
    if not trend_insights:
        return []

    hypotheses = []

    for insight in trend_insights:
        if not insight:
            continue

        if isinstance(insight, dict):
            description = (
                insight.get("description")
                or insight.get("finding")
                or insight.get("pattern")
                or ""
            )
            evidence = insight.get("evidence") or ""
        else:
            description = str(insight)
            evidence = ""

        description = str(description).strip()

        if not description:
            continue

        hypotheses.append({
            "pattern": description,
            "evidence": str(evidence).strip(),
            "possible_factors": [
                "meal timing",
                "activity",
                "daily routine",
                "other contextual factors",
            ],
            "confidence": "observational",
            "note": (
                "These are possible factors to discuss, not explanations "
                "or diagnoses."
            ),
        })

    return hypotheses

def generate_questions(hypotheses):
    """Create follow-up questions based on the observed hypotheses."""
    if not hypotheses:
        return []

    questions = []

    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue

        pattern = hypothesis.get("pattern", "")
        pattern = str(pattern).strip()

        if not pattern:
            continue

        question = (
            "Have you noticed anything in your meals, activity, or routine "
            f"that happens around this pattern: {pattern}?"
        )

        questions.append(question)

    return questions
