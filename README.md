# Glucose Review

A small Flask project for looking through Dexcom-style CGM exports. Upload a CSV,
choose the glucose range you use, and the app builds a report with time in range,
average readings, daily timing patterns, and notes about the quality of the export.

Research paper: https://docs.google.com/document/d/10srSvTwi8gwdgswgEZNYoxfbTFUUfGuckuzQec5m_Ho/edit?usp=sharing

The goal is to make a CGM file easier to talk through. It does not diagnose a
condition or recommend treatment changes.

## Run it locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Then open the local address Flask prints in the terminal.

## What to upload

The main upload is a Dexcom-style CSV export. On the upload page, enter the target
range you want the report to use. The range is not guessed from the data.

You can also add a simple event log as a CSV. It needs these columns:

```text
timestamp,event_type
```

For meals, use `meal` as the event type. `label` and `carbohydrate_grams` are also
accepted if you have them. The report only connects readings to events that were
actually logged; it does not assume a meal, medication, or activity caused a change.

## API

`POST /api/analyze` accepts the same multipart form fields as the upload page and
returns the report as JSON. This is useful if you want to use the calculations in
another interface.

## Optional review notes

If `GEMINI_API_KEY` is available, the app can add short plain-language review notes.
Only a minimized summary of the calculated report is sent; free-text notes and raw
timestamp-level readings stay local.

For local layout checks without an API key:

```bash
export MOCK_AI=true
python3 app.py
```

The sample notes are for development only. To use the configured service instead,
set `MOCK_AI=false` and provide the key through your shell or a local `.env` file.
The `.env` file should stay out of Git.

## Notes

This is a prototype for personal review and care-team conversations. A production
version would need clinical validation, privacy and security review, access controls,
and appropriate data-retention practices.