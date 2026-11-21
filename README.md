# EventMate AI Event Planner

EventMate helps students, families, and campus groups plan birthdays, parties, and university events. It creates an event record, builds a guest list, estimates a budget, checks a real Open-Meteo forecast for outdoor plans, and checks public holidays through Nager.Date. Before it cancels an event, LangGraph pauses and asks the user to approve or reject the action.

## What is included

- `agent.ipynb` — Colab notebook with the implementation, graph diagram, guided tests, and evaluation table.
- `agent.py` — tools, session-isolated event storage, and LangGraph `build_graph()` implementation.
- `app.py` — Streamlit chat application with conversation history and cancellation approval buttons.
- `main.py` — terminal chat application with hidden API-key entry and approval/rejection.
- `tests/test_agent.py` — automated tests for event creation, guest management, budget estimates, memory, external API parsing, cancellation approval, rejection, and session isolation.
- `requirements.txt` — Python dependencies.
- `assignment_checklist.md` — mapping from source requirements to files and checks.
- `presentation.md` — short presentation and live demo guide in clear English.

## Architecture

The graph has an `assistant` node and a `tools` node. The assistant uses ChatGroq with `llm.bind_tools(...)`; conditional routing sends tool calls to the tools node and returns their results to the assistant. A `StateGraph` stores the message history. `InMemorySaver` checkpoints each conversation by `thread_id`, so a later message in the same session can refer to earlier events. A separate in-memory event store uses that same thread ID as its key, keeping each conversation's event details separate.

`cancel_event` calls LangGraph's `interrupt()` before removing any event. The app and CLI resume the exact conversation with `Command(resume=True)` for approval or `Command(resume=False)` for rejection. Open-Meteo and Nager.Date are real, key-free public APIs. Weather forecasts are date-limited; the tool reports when a forecast is unavailable instead of inventing one.

## Requirements

- Python 3.11 or newer
- A Groq account and API key for model calls
- Internet access for Groq, Open-Meteo, and Nager.Date
- Google account for Colab, and GitHub account for repository submission/deployment

## Run locally on Windows

Open PowerShell in this project folder and run these commands one at a time:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The CLI asks for your Groq key without showing it:

```powershell
.\.venv\Scripts\python.exe main.py
```

To run Streamlit locally, create `.streamlit\secrets.toml` with this line:

```toml
GROQ_API_KEY = "paste-your-own-key-here"
```

Then launch:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Never commit `.streamlit/secrets.toml`, `.env`, or a real key. They are excluded by `.gitignore`.

## Run in Google Colab

1. Upload `agent.ipynb` to Colab, or open it from Google Drive.
2. In the left sidebar, open **Secrets** and add `GROQ_API_KEY`; enable notebook access.
3. Run the cells from top to bottom. The install cell installs packages and the key cell reads the key without printing it.
4. The notebook contains separate demonstration cells. Cells that call Groq need the key; the weather and holiday cells need internet access.
5. Read the evaluation table carefully. Its initial status is `NOT RUN` because results must come from a real notebook execution, not from a prepared example.

## Test the project

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The automated suite uses a scripted local model for repeatable graph checks and mocked HTTP responses for unit testing. This does not claim that live APIs or Groq were contacted by the test suite. The Colab notebook includes separate live API cells and agent queries for you to execute. Record their actual outcomes in its evaluation table.

## Colab and submission checklist

The notebook starter requests at least two real external services; EventMate uses Open-Meteo and Nager.Date. The PDF lists at least one external API among its minimum passing requirements. The project includes both services, at least five test queries, an approval example, and a rejection example.

See [`assignment_checklist.md`](assignment_checklist.md) for the line-by-line requirement mapping and current verification status.

## GitHub upload for a beginner

1. Sign in at GitHub and use **New repository**. Name it `ai-event-planner`; choose Public if your lecturer needs access and your course permits public projects.
2. Do not add your API key to any file. Upload the files in this folder, including `README.md`, `requirements.txt`, `agent.py`, `app.py`, `main.py`, and `agent.ipynb`. Include `.gitignore` and `tests/` too.
3. Before committing, inspect the file list and search every file for `gsk_` and for `GROQ_API_KEY = "` followed by anything other than a placeholder. A real key must never appear in the repository.
4. Commit the files. Copy the repository URL and send that URL as the assignment asks; do not submit only a ZIP file.
5. If you use Git locally instead: install Git from its official website, open PowerShell in the project folder, then run `git init`, `git add .`, `git commit -m "Add EventMate project"`, add the repository URL with `git remote add origin YOUR_REPOSITORY_URL`, and push the current branch. GitHub's browser upload is also acceptable for a first submission.

## Deploy to Streamlit Community Cloud

1. Push the project to GitHub and sign in to Streamlit Community Cloud with GitHub.
2. Create an app from the repository, choose the branch, and set the main file to `app.py`.
3. In the app's **Settings → Secrets**, add `GROQ_API_KEY = "your_real_key"`. Enter the key only in Streamlit's secret field, never in GitHub.
4. Deploy and wait for the build to finish. If it fails, open the deployment logs and fix the first relevant error.
5. Open the public app URL. Test an event, a guest, a weather request, and both cancellation buttons. Confirm that the app's GitHub repository and deployed URL are accessible to your lecturer.

## Limitations

- Groq API usage is subject to the account's current model availability and rate limits.
- Weather forecasts only cover dates supported by Open-Meteo's forecast service. A location must be resolvable by its geocoder.
- Nager.Date coverage varies by country and year.
- `InMemorySaver` and the event store lose their data when the process restarts. This is appropriate for a class demo, not permanent event storage. SQLite or a hosted database would be a future improvement.
- Event data is isolated by random session/thread IDs, but the demo has no user login, durable database, or production privacy controls.
- Tool selection is performed by an LLM and can occasionally be wrong; check event dates, amounts, and locations before relying on a plan.
