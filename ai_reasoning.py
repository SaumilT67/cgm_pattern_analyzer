"""Guarded server-side Gemini review for a CGM evidence report."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import time
import socket

MOCK_AI = os.getenv("MOCK_AI", "false").lower() == "true"

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _safe_payload(report):
    """Build the limited evidence package that can be sent to the AI reviewer."""
    patient_context = report.get("patient_context") or {}
    observed_episodes = report.get("observed_episodes") or {}

    above_episodes = observed_episodes.get("above_target") or []
    below_episodes = observed_episodes.get("below_target") or []

    payload = {
        "target_range_mg_dl": report.get("target_range_mg_dl"),
        "data_quality": report.get("data_quality"),
        "measured_metrics": report.get("measured_metrics"),
        "time_of_day_observations": report.get("time_of_day_observations"),
        "usual_meal_times": patient_context.get("usual_meal_times"),
        "usual_meal_time_observations": report.get(
            "usual_meal_time_observations"
        ),
        "recorded_meal_associations": report.get(
            "recorded_event_associations"
        ),
        "episode_counts": {
            "above_target": len(above_episodes),
            "below_target": len(below_episodes),
        },
        "limitations": report.get("limitations"),
    }

    return payload


def _prompt(report):
    """Create the instructions and evidence used for the Gemini review."""
    payload = _safe_payload(report)
    evidence = json.dumps(
        payload,
        separators=(",", ":"),
        default=str,
    )

    instructions = [
        "You are a cautious clinical decision-support writing assistant.",
        "Review only the supplied CGM evidence.",
        "Do not diagnose or prescribe.",
        "Do not recommend insulin or medication changes.",
        "Do not tell a person what to eat.",
        "Do not give urgent-care instructions.",
        "Do not claim that a specific factor caused a glucose pattern.",
        "Use wording such as 'may be worth discussing' when appropriate.",
        "Explain what information is missing when the evidence is limited.",
        "A usual meal time is only a general schedule, not proof that a meal occurred.",
        "Only describe a meal as recorded when it appears in recorded_meal_associations.",
        "Do not invent facts, dates, readings, patient history, or numerical results.",
        "State when data coverage or context is limited.",
        "Use language that is understandable to a patient and useful for a clinician.",
        "Return only valid JSON.",
        "Do not use markdown or add text before or after the JSON.",
        "Keep all strings concise.",
    ]

    required_format = (
        '{"plain_language_summary":"string",'
        '"observations":[{"finding":"string","evidence":"string",'
        '"timing_note":"string"}],'
        '"possible_explanations_to_discuss":[{"topic":"string",'
        '"why_it_may_be_relevant":"string",'
        '"what_would_help_confirm":"string"}],'
        '"questions_for_care_team":["string"],'
        '"boundary_note":"string"}'
    )

    rules = "\n".join(f"- {item}" for item in instructions)

    return (
        f"{rules}\n\n"
        f"Return exactly this JSON structure:\n{required_format}\n\n"
        f"Evidence report:\n{evidence}"
    )

def _validate_review(review):
    """Check that the AI response has the expected top-level structure."""
    expected_types = {
        "plain_language_summary": str,
        "observations": list,
        "possible_explanations_to_discuss": list,
        "questions_for_care_team": list,
        "boundary_note": str,
    }

    if not isinstance(review, dict):
        raise ValueError("Gemini returned an unexpected review format.")

    for field_name, expected_type in expected_types.items():
        value = review.get(field_name)

        if not isinstance(value, expected_type):
            raise ValueError(
                "Gemini returned an unexpected review format."
            )

    return review

def mock_review():
    """Return representative review data for local interface testing."""
    observations = [
        {
            "finding": "Afternoon and evening glucose elevations",
            "evidence": (
                "Average glucose was higher between afternoon and evening "
                "periods compared with overnight readings."
            ),
            "timing_note": (
                "This pattern appeared repeatedly across the reviewed CGM period."
            ),
        },
        {
            "finding": "Repeated glucose rises after meal windows",
            "evidence": (
                "Several increases above target occurred after usual meal-time "
                "periods."
            ),
            "timing_note": (
                "These patterns were observed within the hours following "
                "meal-time windows."
            ),
        },
        {
            "finding": "Elevated glucose variability",
            "evidence": (
                "Glucose levels showed noticeable fluctuations throughout "
                "the monitoring period."
            ),
            "timing_note": (
                "Variability reflects changes across all available CGM readings."
            ),
        },
    ]

    discussion_topics = [
        {
            "topic": "Evening glucose patterns",
            "why_it_may_be_relevant": (
                "Evening changes can be influenced by several factors such as "
                "meals, activity, and daily routines."
            ),
            "what_would_help_confirm": (
                "Additional information about meals, activity, and medication "
                "timing would provide more context."
            ),
        },
        {
            "topic": "Post-meal glucose changes",
            "why_it_may_be_relevant": (
                "Repeated rises after meal periods may indicate a pattern "
                "worth reviewing."
            ),
            "what_would_help_confirm": (
                "Detailed meal timing and nutrition information could help "
                "explain these changes."
            ),
        },
    ]

    questions = [
        "What patterns in my CGM data should we monitor over time?",
        "What additional information would help explain my glucose changes?",
        "How can I better understand repeated highs during certain times of day?",
    ]

    return {
        "status": "available",
        "model": "mock",
        "plain_language_summary": (
            "Your glucose data shows repeated patterns of higher readings "
            "during afternoon and evening hours compared with overnight. "
            "Several trends were detected that may be worth discussing "
            "with your care team."
        ),
        "observations": observations,
        "possible_explanations_to_discuss": discussion_topics,
        "questions_for_care_team": questions,
        "boundary_note": (
            "This is a mock AI review used for interface testing. It "
            "summarizes glucose patterns only and does not provide diagnosis "
            "or treatment recommendations."
        ),
    }

def generate_gemini_review(report):
    """Request a structured Gemini review while keeping failures contained."""
    if MOCK_AI:
        return mock_review()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"status": "not_configured"}

    prompt = _prompt(report)

    request_body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 2048,
            "thinkingConfig": {
                "thinkingBudget": 0
            },
        },
    }

    request = Request(
        API_URL.format(model=MODEL),
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        response_body = None

        for attempt_number in range(3):
            try:
                with urlopen(request, timeout=120) as response:
                    response_body = json.loads(
                        response.read().decode("utf-8")
                    )
                break

            except (TimeoutError, socket.timeout, HTTPError) as error:
                temporary_http_error = (
                    isinstance(error, HTTPError)
                    and error.code == 503
                )

                if isinstance(error, HTTPError) and not temporary_http_error:
                    raise

                if attempt_number == 2:
                    raise

                delay = 10 * (attempt_number + 1)

                print(
                    f"Gemini temporary failure ({type(error).__name__}). "
                    f"Retry {attempt_number + 1}/3 in {delay}s..."
                )

                time.sleep(delay)

        if response_body is None:
            raise TimeoutError("Gemini failed after 3 retries")

        response_text = (
            response_body["candidates"][0]["content"]["parts"][0]["text"]
        )

        response_text = response_text.strip()
        json_start = response_text.find("{")
        json_end = response_text.rfind("}")

        if json_start < 0 or json_end < 0 or json_end < json_start:
            return {
                "status": "unavailable",
                "message": (
                    "Gemini returned an incomplete or invalid response."
                ),
            }

        json_text = response_text[json_start:json_end + 1]

        try:
            parsed_review = json.loads(json_text)
        except json.JSONDecodeError:
            return {
                "status": "unavailable",
                "message": (
                    "Gemini returned an incomplete or invalid response."
                ),
            }

        review = _validate_review(parsed_review)
        review["status"] = "available"
        review["model"] = MODEL

        return review

    except (
        HTTPError,
        URLError,
        TimeoutError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return {
            "status": "unavailable",
            "message": f"AI review failed: {str(error)}",
        }