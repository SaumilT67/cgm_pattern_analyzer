import pandas as pd
import plotly.express as px


def load_csv(filepath):
    """Read a CGM CSV while handling files with or without a UTF-8 BOM."""
    encoding = "utf-8-sig"
    data = pd.read_csv(filepath, encoding=encoding)
    return data

def clean_dexcom_data(df):
    """Convert supported CGM export columns into a clean analysis table."""
    working = df.dropna(how="all").copy()

    time_columns = [
        "Timestamp",
        "Timestamp (YYYY-MM-DDThh:mm:ss)",
        "timestamp",
        "Date",
        "time",
        "Time",
    ]
    glucose_columns = [
        "Glucose Value",
        "GlucoseValue",
        "glucose",
        "Glucose",
        "glucose_mg_dL",
        "Sensor Glucose (mg/dL)",
        "Glucose Value (mg/dL)",
        "mg/dL",
        "Value",
    ]

    time_col = next(
        (column for column in time_columns if column in working.columns),
        None,
    )
    glucose_col = next(
        (column for column in glucose_columns if column in working.columns),
        None,
    )

    if time_col is None or glucose_col is None:
        raise ValueError(
            f"Missing required columns. Found: {working.columns.tolist()}"
        )

    timestamps = pd.to_datetime(
        working[time_col],
        errors="coerce",
    )

    glucose_text = (
        working[glucose_col]
        .astype("string")
        .str.strip()
    )
    glucose_values = pd.to_numeric(
        glucose_text,
        errors="coerce",
    )

    timestamp_present = timestamps.notna()
    censored_high = (
        glucose_text.str.lower().eq("high")
        & timestamp_present
    )
    censored_low = (
        glucose_text.str.lower().eq("low")
        & timestamp_present
    )
    usable_glucose = timestamp_present & glucose_values.notna()

    cleaned = pd.DataFrame({
        "timestamp": timestamps[usable_glucose],
        "glucose": glucose_values[usable_glucose],
    })

    cleaned = (
        cleaned
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    event_col = next(
        (
            column
            for column in ["Event Type", "event_type", "EventType"]
            if column in working.columns
        ),
        None,
    )

    event_counts = {}
    if event_col is not None:
        labels = (
            working.loc[timestamp_present, event_col]
            .fillna("Unspecified")
            .astype(str)
            .str.strip()
        )
        labels = labels[~labels.str.upper().eq("EGV")]

        event_counts = {
            str(label): int(count)
            for label, count in labels.value_counts().items()
        }

    censored_readings = []

    for row_index in working.index[censored_high | censored_low]:
        censored_readings.append({
            "timestamp": timestamps.loc[row_index].isoformat(),
            "reported_value": str(glucose_text.loc[row_index]),
        })

    device_col = next(
        (
            column
            for column in ["Device Info", "device_info", "Device"]
            if column in working.columns
        ),
        None,
    )

    devices = []
    if device_col is not None:
        devices = sorted({
            str(value).strip()
            for value in working[device_col].dropna()
            if str(value).strip()
        })

    cleaned.attrs["source_summary"] = {
        "source_format": (
            "Dexcom Clarity export"
            if "Event Type" in working.columns
            else "CGM CSV"
        ),
        "rows_in_file": int(len(working)),
        "numeric_glucose_readings_used": int(usable_glucose.sum()),
        "censored_high_readings": int(censored_high.sum()),
        "censored_low_readings": int(censored_low.sum()),
        "censored_glucose_readings": censored_readings,
        "timestamped_non_glucose_events": event_counts,
        "devices_listed_in_export": devices,
        "non_reading_rows": int(
            len(working)
            - usable_glucose.sum()
            - censored_high.sum()
            - censored_low.sum()
        ),
        "note": (
            "Numeric glucose readings are used for charts and calculations. "
            "Literal High/Low readings and timestamped non-glucose events are "
            "retained as separate source information because no exact glucose "
            "value was supplied."
        ),
    }

    return cleaned


def process_pipeline(filepath):
    """Load a CGM file and pass it through the cleaning step."""
    raw_data = load_csv(filepath)
    cleaned_data = clean_dexcom_data(raw_data)
    return cleaned_data


def load_event_log(filepath):
    """Read an optional event log and standardize its supported fields."""
    events = pd.read_csv(filepath)
    events = events.dropna(how="all")

    aliases = {
        "timestamp": ["timestamp", "Timestamp", "time", "Time", "Date"],
        "event_type": ["event_type", "Event Type", "type", "Type"],
        "label": ["label", "Label", "description", "Description"],
        "carbohydrate_grams": [
            "carbohydrate_grams",
            "carbs_g",
            "Carbs (g)",
            "carbs",
        ],
    }

    resolved = {}

    for field, possible_names in aliases.items():
        resolved[field] = None

        for name in possible_names:
            if name in events.columns:
                resolved[field] = name
                break

    if resolved["timestamp"] is None or resolved["event_type"] is None:
        raise ValueError("Event log needs timestamp and event_type columns.")

    rename_map = {}
    for field, source_column in resolved.items():
        if source_column is not None:
            rename_map[source_column] = field

    events = events.rename(columns=rename_map)

    events["timestamp"] = pd.to_datetime(
        events["timestamp"],
        errors="coerce",
    )
    events["event_type"] = (
        events["event_type"]
        .astype(str)
        .str.strip()
    )

    if "label" not in events.columns:
        events["label"] = ""

    if "carbohydrate_grams" not in events.columns:
        events["carbohydrate_grams"] = None

    events["carbohydrate_grams"] = pd.to_numeric(
        events["carbohydrate_grams"],
        errors="coerce",
    )

    valid_events = events.dropna(subset=["timestamp"])

    return valid_events.sort_values("timestamp")

def create_glucose_graph(df):
    """Create the interactive glucose-over-time graph used by the app."""
    figure = px.line(
        data_frame=df,
        x="timestamp",
        y="glucose",
        title="CGM Glucose Over Time",
    )

    html = figure.to_html(full_html=False)
    return html