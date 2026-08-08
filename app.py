from flask import Flask, jsonify, render_template, request
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import certifi


load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()

print("GEMINI_API_KEY loaded:", os.getenv("GEMINI_API_KEY") is not None)
print("Model:", os.getenv("GEMINI_MODEL"))

def _load_local_env():
    """Load local development secrets without overriding real deployment env vars."""
    env_file = Path(__file__).with_name(".env")
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


_load_local_env()

from pipeline import create_glucose_graph, load_event_log, process_pipeline
from analysis import build_clinical_evidence_report
from ai_reasoning import generate_gemini_review

app = Flask(__name__)

UPLOAD_FOLDER = "/tmp"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        report, df = _analyze_request()
    except (KeyError, ValueError) as error:
        return render_template("index.html", error=str(error)), 400
    if request.path == "/api/analyze":
        return jsonify(report)
    return render_template("report.html", report=report, graph_html=create_glucose_graph(df))


def _analyze_request():
    file = request.files.get("file")
    if not file or not file.filename:
        raise ValueError("Please upload a CGM CSV file.")
    target_low, target_high = _parse_targets()
    ##os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filepath = _save_temporary_upload(file)
    event_path = None
    try:
        events = None
        event_file = request.files.get("event_file")
        if event_file and event_file.filename:
            event_path = _save_temporary_upload(event_file)
            events = load_event_log(event_path)
        context = {
            "diabetes_type": request.form.get("diabetes_type", "").strip() or None,
            "therapy_context": request.form.get("therapy_context", "").strip() or None,
            "clinician_notes": request.form.get("clinician_notes", "").strip() or None,
        }
        usual_meal_times = {
            "breakfast": request.form.get("usual_breakfast_time", "").strip(),
            "lunch": request.form.get("usual_lunch_time", "").strip(),
            "dinner": request.form.get("usual_dinner_time", "").strip(),
        }
        usual_meal_times = {meal: time for meal, time in usual_meal_times.items() if time}
        if usual_meal_times:
            context["usual_meal_times"] = {
                "times": usual_meal_times,
                "note": "General schedule supplied by the user; it does not confirm that a meal occurred.",
            }
        context = {key: value for key, value in context.items() if value}
        df = process_pipeline(filepath)
        report = build_clinical_evidence_report(df, target_low, target_high, events, context)
        report["ai_review"] = generate_gemini_review(report)
        return report, df
    finally:
        for path in (filepath, event_path):
            if path and os.path.exists(path):
                os.remove(path)


def _parse_targets():
    """Read explicit targets without deriving them from demographic or CGM data."""
    try:
        target_low = float(request.form["target_low"])
        target_high = float(request.form["target_high"])
    except ValueError as error:
        raise ValueError("Target limits must be numeric.") from error
    if not 0 < target_low < target_high:
        raise ValueError("The lower target must be greater than 0 and lower than the upper target.")
    return target_low, target_high


def _save_temporary_upload(file_storage):
    """Store an upload only long enough to parse it; avoid filename collisions/retention."""
    suffix = os.path.splitext(file_storage.filename)[1].lower() or ".csv"
    with tempfile.NamedTemporaryFile(dir=app.config["UPLOAD_FOLDER"], suffix=suffix, delete=False) as temporary:
        file_storage.save(temporary)
        return temporary.name


@app.route("/api/analyze", methods=["POST"])
def analyze_api():
    return upload_file()


if __name__ == "__main__":
    app.run(debug=True)

