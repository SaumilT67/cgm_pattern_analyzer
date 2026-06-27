from flask import Flask, render_template, request
import os
from pipeline import process_pipeline, create_glucose_graph
from analysis import calculate_daily_metrics, analyze_trends, detect_patterns, build_glucose_behavior_model, analyze_time_segments, detect_spike_events, analyze_recovery_behavior
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

    time_analysis = analyze_time_segments(df)

    # STEP 3: trends
    trend_insights = analyze_trends(daily_metrics)

    # STEP 4: behavior reasoning (moved out of app.py)
    behavior = generate_behavior_hypotheses(trend_insights, daily_metrics)

    # STEP 5: AI-style questions (moved out of app.py)
    questions = generate_questions(behavior)

    spike_events = detect_spike_events(df)

    recovery_stats = analyze_recovery_behavior(df, spike_events)

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

    time_html = ""

    for period, stats in time_analysis.items():
        time_html += f"""
        <b>{period.replace("_", " ").title()}</b><br>
        Average Glucose: {stats["average_glucose"]}<br>
        Variability: {stats["variability"]}<br>
        High Events: {stats["high_events"]}<br>
        Low Events: {stats["low_events"]}<br>
        Time in Range: {stats["time_in_range"]}%<br><br>
        """

    spike_html = ""

    for s in spike_events:
        spike_html += f"""
        <b>Spike Event</b><br>
        Start: {s['start']}<br>
        Peak: {s['peak']} mg/dL<br>
        Duration: {s['duration_min']} min<br><br>
        """

    recovery_html = f"""

        <b>Average Recovery Time:</b> {recovery_stats['avg_recovery_time_min']} min<br>
        <b>Failed Recoveries:</b> {recovery_stats['failed_recoveries']}<br>
        <b>Rebound Lows:</b> {recovery_stats['rebound_low_events']}<br>
        <b>Total Spikes Analyzed:</b> {recovery_stats['total_spikes_analyzed']}<br>
        """
        

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

        <h3>Time of Day Analysis</h3>
        {time_html}
    
        <!--
        <h3>Spike Events</h3>
        spike_html
        -->

        <h3>Recovery Behavior</h3>
        {recovery_html}

        <h3>Behavior Hypotheses</h3>
        {behavior_html}

        <h3>Follow-Up Questions</h3>
        {questions_html}   
    
        """


if __name__ == "__main__":
    app.run(debug=True)