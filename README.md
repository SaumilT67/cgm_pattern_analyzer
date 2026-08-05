# CGM evidence review prototype

This Flask app converts Dexcom-style CGM CSV data into an evidence-first report.
It reports measured glucose metrics, data-quality limitations, distinct threshold
episodes, and associations with *recorded* meal events. It deliberately does not
guess meal times, medication dosing, activity, symptoms, or causes from a CGM trace.

## Using the report

- Enter the patient-specific target range at upload time; it is never inferred.
- Optionally upload a timestamped event-log CSV with `timestamp,event_type` and,
  when available, `label,carbohydrate_grams`. Only `event_type=meal` is used for
  meal associations.
- Use `POST /api/analyze` with the same multipart fields to get the complete
  structured JSON payload for an AI or other clinical-review system.

The JSON explicitly separates measured observations, recorded context, questions
for review, and limitations. Any downstream AI should preserve those labels and
must not convert a correlation into a cause or medication advice.

## Optional Gemini review

The report includes a guarded Gemini review only when the server has a
`GEMINI_API_KEY` environment variable. On macOS with zsh, set it in the terminal
that starts Flask (do not put it in this repository or paste it into the app):

```sh
export GEMINI_API_KEY='your-new-key'
python3 app.py
```

### Run from VS Code

1. In the VS Code Explorer, create a file named `.env` in the project root.
2. Add one line: `GEMINI_API_KEY=your-new-key` (replace only the value).
3. Open **Run and Debug** in VS Code, choose **Run Glucose Review**, and click
   the green play button. The checked-in `.vscode/launch.json` loads `.env` only
   for that local run.

The app also reads a project-root `.env` file when it starts, so this works with
VS Code's regular Run button as well. Restart the app after creating or changing
the file.

`.env` is ignored by Git. Do not paste the key into any Python, HTML, or tracked
configuration file.

The integration sends a minimized evidence summary, not free-text reviewer notes
or raw timestamp-level readings. It asks Gemini for plain-language observations,
uncertainties, and questions for a care team; it prohibits diagnosis, treatment,
diet, or medication recommendations. Set `GEMINI_MODEL` only if you need to
override the default `gemini-2.5-flash`.

## Clinical and privacy boundary

This is a prototype, not a diagnosis or treatment system and not, by itself,
HIPAA-compliant or a regulated medical device. It must not direct medication
changes. A production clinical deployment requires clinical validation, human
oversight, role-based access, audit logging, appropriate data retention controls,
security assessment, and applicable regulatory/privacy review.
