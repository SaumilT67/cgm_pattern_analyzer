"""Guarded server-side Gemini review for a CGM evidence report."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import time
import socket
from click import prompt

MOCK_AI = os.getenv("MOCK_AI", "false").lower() == "true"

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _safe_payload(report):
    """Minimize data sent to the model; free-text notes and raw reading timestamps stay local."""
    context = report.get("patient_context", {})
    return {
        "target_range_mg_dl": report.get("target_range_mg_dl"),
        "data_quality": report.get("data_quality"),
        "measured_metrics": report.get("measured_metrics"),
        "time_of_day_observations": report.get("time_of_day_observations"),
        "usual_meal_times": context.get("usual_meal_times"),
        "usual_meal_time_observations": report.get("usual_meal_time_observations"),
        "recorded_meal_associations": report.get("recorded_event_associations"),
        "episode_counts": {
            "above_target": len(report.get("observed_episodes", {}).get("above_target", [])),
            "below_target": len(report.get("observed_episodes", {}).get("below_target", [])),
        },
        "limitations": report.get("limitations"),
    }


def _prompt(report):
    evidence = json.dumps(_safe_payload(report), separators=(",", ":"), default=str)
    return f"""You are a cautious clinical decision-support writing assistant. Review only the supplied CGM evidence.

Rules:
- Do not diagnose, prescribe, recommend insulin/medication changes, tell a person what to eat, or give urgent-care instructions.
- Do not claim a cause. Use phrases such as 'may be worth discussing' and explain what data is missing.
- A usual meal time is a general schedule, not a meal record. Never say a meal happened unless it appears in recorded_meal_associations.
- Do not invent facts, dates, readings, patient history, or numerical results.
- If data coverage or context is limited, say so.
- Keep language understandable to a patient and useful for a clinician.

Return only valid JSON.

Important:
- Do not include any text before the JSON.
- Do not include any text after the JSON.
- Do not use markdown.
- Do not say "Here is the JSON requested".
- No introduction.
- No explanation.
- No markdown.
- No extra characters.
- The first character must be {{
- The last character must be }}

Keep all strings concise.
Return exactly these fields:
{{"plain_language_summary":"string","observations":[{{"finding":"string","evidence":"string","timing_note":"string"}}],"possible_explanations_to_discuss":[{{"topic":"string","why_it_may_be_relevant":"string","what_would_help_confirm":"string"}}],"questions_for_care_team":["string"],"boundary_note":"string"}}

Evidence report:
{evidence}"""


def _validate_review(review):
    required = {
        "plain_language_summary": str,
        "observations": list,
        "possible_explanations_to_discuss": list,
        "questions_for_care_team": list,
        "boundary_note": str,
    }
    if not isinstance(review, dict) or any(not isinstance(review.get(key), value_type) for key, value_type in required.items()):
        raise ValueError("Gemini returned an unexpected review format.")
    return review

def mock_review():
    return {
        "status": "available",
        "model": "mock",

        "plain_language_summary":
            "Your glucose data shows repeated patterns of higher readings during afternoon and evening hours compared with overnight. Several trends were detected that may be worth discussing with your care team.",

        "observations": [
            {
                "finding": "Afternoon and evening glucose elevations",
                "evidence":
                    "Average glucose was higher between afternoon and evening periods compared with overnight readings.",
                "timing_note":
                    "This pattern appeared repeatedly across the reviewed CGM period."
            },
            {
                "finding": "Repeated glucose rises after meal windows",
                "evidence":
                    "Several increases above target occurred after usual meal-time periods.",
                "timing_note":
                    "These patterns were observed within the hours following meal-time windows."
            },
            {
                "finding": "Elevated glucose variability",
                "evidence":
                    "Glucose levels showed noticeable fluctuations throughout the monitoring period.",
                "timing_note":
                    "Variability reflects changes across all available CGM readings."
            }
        ],

        "possible_explanations_to_discuss": [
            {
                "topic": "Evening glucose patterns",
                "why_it_may_be_relevant":
                    "Evening changes can be influenced by several factors such as meals, activity, and daily routines.",
                "what_would_help_confirm":
                    "Additional information about meals, activity, and medication timing would provide more context."
            },
            {
                "topic": "Post-meal glucose changes",
                "why_it_may_be_relevant":
                    "Repeated rises after meal periods may indicate a pattern worth reviewing.",
                "what_would_help_confirm":
                    "Detailed meal timing and nutrition information could help explain these changes."
            }
        ],

        "questions_for_care_team": [
            "What patterns in my CGM data should we monitor over time?",
            "What additional information would help explain my glucose changes?",
            "How can I better understand repeated highs during certain times of day?"
        ],

        "boundary_note":
            "This is a mock AI review used for interface testing. It summarizes glucose patterns only and does not provide diagnosis or treatment recommendations."
    }

def generate_gemini_review(report):

    if MOCK_AI:
        return mock_review()

    print("Inside ai_reasoning.py")
    print("API KEY:", os.getenv("GEMINI_API_KEY"))

    """Return a parsed review or a safe status object; never expose the API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"status": "not_configured"}
    
    prompt = _prompt(report)

    print("PROMPT LENGTH:", len(prompt))

    request_body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "maxOutputTokens": 2048, "thinkingConfig": {
        "thinkingBudget": 0}},
    }
    request = Request(
        API_URL.format(model=MODEL),
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        body = None

        for attempt in range(3):
            try:
                with urlopen(request, timeout=120) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    break

            except (TimeoutError, socket.timeout, HTTPError) as e:

                # Retry only temporary failures
                if isinstance(e, HTTPError) and e.code != 503:
                    raise

                if attempt < 2:
                    wait_time = 10 * (attempt + 1)
                    print(
                        f"Gemini temporary failure ({type(e).__name__}). "
                        f"Retry {attempt + 1}/3 in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    raise


        if body is None:
            raise TimeoutError("Gemini failed after 3 retries")

        print("FULL GEMINI RESPONSE:")
        print(json.dumps(body, indent=2))

        text = body["candidates"][0]["content"]["parts"][0]["text"]

        print("GEMINI RAW RESPONSE:")
        print(text)

        try:
            # Remove any accidental text before or after the JSON object
            text = text.strip()

            start = text.find("{")
            end = text.rfind("}")

            if start == -1 or end == -1:
                raise json.JSONDecodeError(
                    "No JSON object found",
                    text,
                    0
                )

            clean_json = text[start:end + 1]

            review_json = json.loads(clean_json)

        except json.JSONDecodeError as e:
            print("INVALID GEMINI JSON:")
            print(e)
            print("RAW RESPONSE:")
            print(text)

            return {
                "status": "unavailable",
                "message": "Gemini returned an incomplete or invalid response."
            }

        review = _validate_review(review_json)

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
    ) as e:

        print("GEMINI ERROR TYPE:", type(e))
        print("GEMINI ERROR:", e)

        if isinstance(e, HTTPError):
            print("HTTP STATUS:", e.code)
            print(e.read().decode("utf-8"))

        return {
            "status": "unavailable",
            "message": f"AI review failed: {str(e)}"
        }