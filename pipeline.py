import pandas as pd
import plotly.express as px


def load_csv(filepath):
    # Clarity exports are UTF-8 with a byte-order mark; utf-8-sig also reads
    # regular UTF-8 files without changing their contents.
    return pd.read_csv(filepath, encoding="utf-8-sig")


def clean_dexcom_data(df):
    df = df.dropna(how="all")

    possible_time_cols = ["Timestamp", "Timestamp (YYYY-MM-DDThh:mm:ss)", "timestamp", "Date", "time", "Time"]
    possible_glucose_cols = [
        "Glucose Value",
        "GlucoseValue",
        "glucose",
        "Glucose",
        "glucose_mg_dL",
        "Sensor Glucose (mg/dL)",
        "Glucose Value (mg/dL)",
        "mg/dL",
        "Value"
    ]

    time_col = next((col for col in possible_time_cols if col in df.columns), None)
    glucose_col = next((col for col in possible_glucose_cols if col in df.columns), None)

    if not time_col or not glucose_col:
        raise ValueError(f"Missing required columns. Found: {df.columns.tolist()}")

    raw = df.copy()
    timestamps = pd.to_datetime(raw[time_col], errors="coerce")
    glucose_text = raw[glucose_col].astype("string").str.strip()
    glucose_values = pd.to_numeric(glucose_text, errors="coerce")

    # Clarity can use literal High/Low values in place of an exact mg/dL value.
    # Preserve their counts, but do not invent numeric values for calculations.
    is_censored_high = glucose_text.str.lower().eq("high") & timestamps.notna()
    is_censored_low = glucose_text.str.lower().eq("low") & timestamps.notna()
    valid_glucose = timestamps.notna() & glucose_values.notna()

    cleaned = pd.DataFrame({"timestamp": timestamps[valid_glucose], "glucose": glucose_values[valid_glucose]})
    cleaned = cleaned.sort_values("timestamp").reset_index(drop=True)

    event_col = next((col for col in ["Event Type", "event_type", "EventType"] if col in raw.columns), None)
    event_counts = {}
    if event_col:
        labels = raw.loc[timestamps.notna(), event_col].fillna("Unspecified").astype(str).str.strip()
        labels = labels[~labels.str.upper().eq("EGV")]
        event_counts = {str(key): int(value) for key, value in labels.value_counts().items()}
    censored = []
    for row_index in raw.index[is_censored_high | is_censored_low]:
        censored.append({
            "timestamp": timestamps.loc[row_index].isoformat(),
            "reported_value": str(glucose_text.loc[row_index]),
        })
    device_col = next((col for col in ["Device Info", "device_info", "Device"] if col in raw.columns), None)
    devices = []
    if device_col:
        devices = sorted({str(value).strip() for value in raw[device_col].dropna() if str(value).strip()})
    cleaned.attrs["source_summary"] = {
        "source_format": "Dexcom Clarity export" if "Event Type" in raw.columns else "CGM CSV",
        "rows_in_file": int(len(raw)),
        "numeric_glucose_readings_used": int(valid_glucose.sum()),
        "censored_high_readings": int(is_censored_high.sum()),
        "censored_low_readings": int(is_censored_low.sum()),
        "censored_glucose_readings": censored,
        "timestamped_non_glucose_events": event_counts,
        "devices_listed_in_export": devices,
        "non_reading_rows": int(len(raw) - valid_glucose.sum() - is_censored_high.sum() - is_censored_low.sum()),
        "note": "Numeric glucose readings are used for charts and calculations. Literal High/Low readings and timestamped non-glucose events are retained as separate source information because no exact glucose value was supplied.",
    }
    return cleaned


def process_pipeline(filepath):
    df = load_csv(filepath)
    df = clean_dexcom_data(df)
    return df


def load_event_log(filepath):
    """Load optional, patient-entered context without guessing any missing events.

    Expected columns: timestamp, event_type (for example `meal`), and optional
    label and carbohydrate_grams. Column-name variants are accepted for usability.
    """
    events = pd.read_csv(filepath).dropna(how="all")
    aliases = {
        "timestamp": ["timestamp", "Timestamp", "time", "Time", "Date"],
        "event_type": ["event_type", "Event Type", "type", "Type"],
        "label": ["label", "Label", "description", "Description"],
        "carbohydrate_grams": ["carbohydrate_grams", "carbs_g", "Carbs (g)", "carbs"],
    }
    renamed = {}
    for standard, choices in aliases.items():
        found = next((column for column in choices if column in events.columns), None)
        if found:
            renamed[found] = standard
    events = events.rename(columns=renamed)
    if "timestamp" not in events.columns or "event_type" not in events.columns:
        raise ValueError("Event log needs timestamp and event_type columns.")
    events["timestamp"] = pd.to_datetime(events["timestamp"], errors="coerce")
    events["event_type"] = events["event_type"].astype(str).str.strip()
    if "label" not in events.columns:
        events["label"] = ""
    if "carbohydrate_grams" not in events.columns:
        events["carbohydrate_grams"] = None
    events["carbohydrate_grams"] = pd.to_numeric(events["carbohydrate_grams"], errors="coerce")
    return events.dropna(subset=["timestamp"]).sort_values("timestamp")


def create_glucose_graph(df):
    fig = px.line(
        df,
        x="timestamp",
        y="glucose",
        title="CGM Glucose Over Time"
    )
    return fig.to_html(full_html=False)
