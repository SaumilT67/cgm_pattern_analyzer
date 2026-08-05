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

## Mock AI Integration

The project currently includes a mock AI system to simulate how the future AI analysis layer will work. Instead of requiring an external AI API during early development, the mock AI generates responses based on the detected glucose patterns, trends, and behavioral insights produced by the analysis pipeline. This allows the interview system and recommendation workflow to be tested before connecting a real LLM API such as OpenAI or Gemini.

The mock AI is controlled through an environment variable:

```bash
export MOCK_AI=true
```

When enabled, the application uses the built-in mock AI responses instead of calling an external AI service. This is useful for development, testing, and running the project without API costs or credentials.

To disable the mock AI and prepare the system for a real AI backend:

```bash
export MOCK_AI=false
```

When disabled, the application will use the production AI pathway (such as an API-based LLM integration) if it has been configured.

This design allows the AI layer to be developed independently from the data analysis pipeline while keeping the system flexible for future integration with real AI models.
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
override the default `gemini-3.5-flash`.



## Clinical and privacy boundary

This is a prototype, not a diagnosis or treatment system and not, by itself,
HIPAA-compliant or a regulated medical device. It must not direct medication
changes. A production clinical deployment requires clinical validation, human
oversight, role-based access, audit logging, appropriate data retention controls,
security assessment, and applicable regulatory/privacy review.
