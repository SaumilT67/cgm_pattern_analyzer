import pandas as pd
import plotly.express as px


# -------------------------
# LOAD DATA
# -------------------------
def load_csv(filepath):
    return pd.read_csv(filepath)


# -------------------------
# CLEAN DEXCOM DATA
# -------------------------
def clean_dexcom_data(df):

    df = df.dropna(how="all")

    # MORE FLEXIBLE COLUMN DETECTION
    possible_time_cols = ["Timestamp", "timestamp", "Date", "time", "Time"]

    possible_glucose_cols = [
        "Glucose Value",
        "GlucoseValue",
        "glucose",
        "Glucose",
        "glucose_mg_dL",
        "Sensor Glucose (mg/dL)",
        "mg/dL",
        "Value"
]

    time_col = next((col for col in possible_time_cols if col in df.columns), None)
    glucose_col = next((col for col in possible_glucose_cols if col in df.columns), None)

    if not time_col or not glucose_col:
        raise ValueError(f"Missing required columns. Found: {df.columns}")

    df = df[[time_col, glucose_col]].copy()
    df.columns = ["timestamp", "glucose"]

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["glucose"] = pd.to_numeric(df["glucose"], errors="coerce")

    df = df.dropna()
    df = df.sort_values("timestamp")

    return df


# -------------------------
# PIPELINE WRAPPER
# -------------------------
def process_pipeline(filepath):
    df = load_csv(filepath)
    df = clean_dexcom_data(df)
    return df


# -------------------------
# GRAPH
# -------------------------
def create_glucose_graph(df):
    fig = px.line(
        df,
        x="timestamp",
        y="glucose",
        title="CGM Glucose Over Time"
    )

    return fig.to_html(full_html=False)