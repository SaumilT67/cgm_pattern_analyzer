from flask import Flask, render_template, request
import os
from pipeline import process_pipeline, create_glucose_graph
from patterns import detect_patterns
from trend_analyzer import calculate_daily_metrics
from multi_day_trends import analyze_trends
from behavior_engine import generate_behavior_hypotheses

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
    daily_metrics = calculate_daily_metrics(df)
    trend_insights = analyze_trends(daily_metrics)
    behavior = generate_behavior_hypotheses(trend_insights, daily_metrics)
    daily_table_html = daily_metrics.to_html(
    index=False,
    classes="table"
)
    graph_html = create_glucose_graph(df)

    insights = detect_patterns(df)

    insight_html = "<br>".join([f"• {i}" for i in insights])

    trend_html = "<br>".join([f"• {t}" for t in trend_insights])

    behavior_html = "<br><br>".join([
        f"<b>{b['pattern']}</b><br>Possible causes:<br>" +
        "<br>".join([f"- {c}" for c in b["possible_causes"]])
        for b in behavior
    ])

            

    return f"""
        <h2>CGM Analysis Complete ✔</h2>

        <h3>Insights</h3>
        {insight_html}

        <h3>Daily Metrics</h3>
        {daily_table_html}

        <h3>Glucose Graph</h3>
        {graph_html}

        <h3>Multi-Day Trends</h3>
        {trend_html}

        <h3>Behavior Hypotheses</h3>
        {behavior_html}
        """

if __name__ == "__main__":
    app.run(debug=True)