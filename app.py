from flask import Flask, render_template, request
import os
from pipeline import process_pipeline, create_glucose_graph
from analysis import calculate_daily_metrics, analyze_trends, detect_patterns, build_glucose_behavior_model
from reasoning import generate_behavior_hypotheses, generate_questions

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

    # STEP 1: clean data
    df = process_pipeline(filepath)

    # STEP 2: daily metrics
    daily_metrics = calculate_daily_metrics(df)

    # STEP 3: trends
    trend_insights = analyze_trends(daily_metrics)

    # STEP 4: behavior reasoning (moved out of app.py)
    behavior = generate_behavior_hypotheses(trend_insights, daily_metrics)

    # STEP 5: AI-style questions (moved out of app.py)
    questions = generate_questions(behavior)

    # STEP 6: visualization
    graph_html = create_glucose_graph(df)

    # STEP 7: outputs
    daily_table_html = daily_metrics.to_html(index=False, classes="table")
    behavior_model = build_glucose_behavior_model(df)
    insights = detect_patterns(df)

    insight_html = "<br>".join([f"• {i}" for i in insights])
    trend_html = "<br>".join([f"• {t}" for t in trend_insights])
    questions_html = "<br>".join([f"• {q}" for q in questions])

    behavior_html = "<br><br>".join([
        f"<b>{b['pattern']}</b><br>" +
        "<br>".join([f"- {c}" for c in b.get("possible_causes", [])])
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

        <h3>Follow-Up Questions</h3>
        {questions_html}
    """


if __name__ == "__main__":
    app.run(debug=True)