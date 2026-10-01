from flask import Flask, jsonify, render_template, request
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import certifi


load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()

def _load_local_env():
    """Load local development secrets without replacing existing variables."""
    env_file = Path(__file__).with_name(".env")

    if not env_file.is_file():
        return

    lines = env_file.read_text(encoding="utf-8").splitlines()

    for raw_line in lines:
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()

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
    """Render the application's main page."""
    page = render_template("index.html")
    return page


@app.route("/upload", methods=["POST"])
def upload_file():
    """Process an uploaded CGM file and return the appropriate result page."""
    try:
        result = _analyze_request()
    except (KeyError, ValueError) as error:
        message = str(error)
        return render_template("index.html", error=message), 400

    report, data = result

    if request.path == "/api/analyze":
        return jsonify(report)

    graph = create_glucose_graph(data)

    return render_template(
        "report.html",
        report=report,
        graph_html=graph,
    )

def _analyze_request():
    """Collect the upload inputs, run the analysis pipeline, and build the report."""
    cgm_file = request.files.get("file")

    if cgm_file is None or not cgm_file.filename:
        raise ValueError("Please upload a CGM CSV file.")

    target_low, target_high = _parse_targets()

    cgm_path = _save_temporary_upload(cgm_file)
    event_path = None

    try:
        event_data = None
        uploaded_events = request.files.get("event_file")

        if uploaded_events is not None and uploaded_events.filename:
            event_path = _save_temporary_upload(uploaded_events)
            event_data = load_event_log(event_path)

        context = {}

        diabetes_type = request.form.get("diabetes_type", "").strip()
        therapy_context = request.form.get("therapy_context", "").strip()
        clinician_notes = request.form.get("clinician_notes", "").strip()

        if diabetes_type:
            context["diabetes_type"] = diabetes_type

        if therapy_context:
            context["therapy_context"] = therapy_context

        if clinician_notes:
            context["clinician_notes"] = clinician_notes

        meal_times = {
            "breakfast": request.form.get(
                "usual_breakfast_time", ""
            ).strip(),
            "lunch": request.form.get(
                "usual_lunch_time", ""
            ).strip(),
            "dinner": request.form.get(
                "usual_dinner_time", ""
            ).strip(),
        }

        meal_times = {
            meal: time
            for meal, time in meal_times.items()
            if time
        }

        if meal_times:
            context["usual_meal_times"] = {
                "times": meal_times,
                "note": (
                    "General schedule supplied by the user; it does not "
                    "confirm that a meal occurred."
                ),
            }

        data = process_pipeline(cgm_path)

        report = build_clinical_evidence_report(
            data,
            target_low,
            target_high,
            event_data,
            context,
        )

        report["ai_review"] = generate_gemini_review(report)

        return report, data

    finally:
        if event_path and os.path.exists(event_path):
            os.remove(event_path)

        if os.path.exists(cgm_path):
            os.remove(cgm_path)


def _parse_targets():
    """Read explicit targets without deriving them from demographic or CGM data."""
    try:
        target_low = float(request.form["target_low"])
        target_high = float(request.form["target_high"])
    except ValueError as error:
        raise ValueError("Target limits must be numeric.") from error
    if target_low <= 0:
        raise ValueError("The lower target must be greater than 0 and lower than the upper target.")
    if target_high <= target_low:
        raise ValueError("The lower target must be greater than 0 and lower than the upper target.")
    return target_low, target_high


def _save_temporary_upload(file_storage):
    """Create a temporary file for an uploaded CGM or event file."""
    filename = file_storage.filename or ""
    extension = Path(filename).suffix.lower()

    if not extension:
        extension = ".csv"

    temporary_file = tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=extension,
        dir=app.config["UPLOAD_FOLDER"],
        delete=False,
    )

    try:
        file_storage.save(temporary_file)
        return temporary_file.name
    finally:
        temporary_file.close()


@app.route("/api/analyze", methods=["POST"])
def analyze_api():
    """Handle API analysis requests through the shared upload workflow."""
    response = upload_file()
    return response

if __name__ == "__main__":
    app.run(debug=True)
