# Assignment Requirement Checklist

This checklist separates the original assignment PDF, the Colab notebook outline, and the student's project instructions. Where they differ, the implementation targets the stricter combined requirement.

| Source requirement | Implementation | Verification | Status |
|---|---|---|---|
| PDF: project title and one-paragraph description | README introduction; notebook opening | Read files | Implemented |
| PDF: setup commands and blank API-key example; no real key | README, notebook, `.gitignore` | Secret scan before GitHub upload | Implemented; secret scan still needed on final repository |
| PDF: document every tool with a docstring | `@tool` functions in `agent.py`; same source in notebook | Inspect tool definitions | Implemented |
| PDF: define State and configure StateGraph | `AgentState`, `build_graph()` in `agent.py` | Inspect code and invoke graph tests | Implemented and locally verified |
| PDF: render graph using `draw_mermaid_png()` | Notebook graph cell | Run notebook cell in Colab | Not yet verified |
| PDF: at least five separate test queries and visible trajectory | Six separate test cells in notebook | Run cells with Groq key and inspect outputs | Cells implemented; notebook trajectories not yet run |
| PDF: destructive action approved | `cancel_event` uses `interrupt()`; notebook approval test | Automated graph test verifies event is removed after resume | Locally verified with scripted test model; Groq notebook demo pending |
| PDF: destructive action denied | Resume with `Command(resume=False)`; notebook rejection test | Automated graph test verifies event remains | Locally verified with scripted test model; Groq notebook demo pending |
| PDF: evaluation table with at least five rows | Notebook table starts with `NOT RUN` entries | Fill with real outcomes after execution | Implemented; results not yet verified |
| PDF: Streamlit app | `app.py` | Run locally and click through chat/approval | Implemented; UI not yet executed |
| PDF: terminal CLI | `main.py` | Run locally and test conversation/approval | Implemented; CLI not yet executed |
| PDF: GitHub repository, README, description, setup, submit repository URL | README upload guide | Student creates repo and shares URL | Not yet completed; requires student's GitHub account |
| PDF minimum: 2 tools, 1 external API, memory, StateGraph, 5 tests, approval | Multiple documented tools, two HTTP APIs, checkpointer, graph, six notebook scenarios, approval/rejection | Seven automated checks plus live service requests | Implemented; local tests and both APIs verified, Colab trajectory results pending |
| Notebook outline: at least 2 real external services | Open-Meteo and Nager.Date tools | Live HTTP calls to both services | Verified from this runtime; rerun from Colab for notebook evidence |
| Student instructions: Groq/ChatGroq and `GROQ_API_KEY` | `ChatGroq`, notebook secret cell, app/CLI key handling | Run with student's Groq key | Implemented; key unavailable here |
| Student instructions: Streamlit approval buttons and isolated sessions | Session UUID/thread ID, approval/rejection controls, keyed event store | Two browser sessions and both decisions | Implemented; interactive UI check remains |
| Student instructions: presentation materials | `presentation.md` | Review/demo rehearsal | Implemented |

## Important source distinction

The PDF is the grading brief. The notebook is a starter outline that adds the stricter requirement of two external services and describes destructive actions generally. The Georgian beginner guide is guidance and examples, not a grading rubric. The student's pasted request adds Groq, specific tool names/features, beginner instructions, and additional project files. This project follows the pasted request while satisfying the stricter external-service count from the notebook.

## Current local verification

- Nine automated unit/graph tests pass using a deterministic model and HTTP response fixtures.
- Open-Meteo returned a forecast for Tbilisi dated 2026-11-21 (14.9°C maximum, 93% maximum precipitation probability).
- Nager.Date returned 17 public holidays for Georgia in 2026.
- Python syntax checks passed for all `.py` files, and JSON plus code-cell syntax checks passed for the 26-cell notebook.

## Not yet verified

- Fresh Colab top-to-bottom execution with the user's Groq key.
- Live Groq tool calling, graph image rendering, and notebook trajectory output.
- Live Open-Meteo and Nager.Date responses from the user's Colab runtime.
- Local Streamlit and CLI interactive behavior on the user's machine.
- GitHub secret scan, repository accessibility, and Streamlit Community Cloud deployment.
