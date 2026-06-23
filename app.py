from flask import Flask, render_template, request
import os
from pipeline import process_pipeline, create_glucose_graph
from patterns import detect_patterns

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files["file"]

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    df = process_pipeline(filepath)
    graph_html = create_glucose_graph(df)

    insights = detect_patterns(df)

    insight_html = "<br>".join([f"• {i}" for i in insights])

    return f"""
    <h2>CGM Analysis Complete ✔</h2>

    <h3>Insights</h3>
    {insight_html}

    <h3>Glucose Graph</h3>
    {graph_html}
    """

if __name__ == "__main__":
    app.run(debug=True)