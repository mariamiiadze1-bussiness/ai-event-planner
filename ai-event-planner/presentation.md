# EventMate Presentation Guide

## Short introduction

Hello. My project is called EventMate. It is an AI assistant that helps students, families, and university groups plan events. It can save event details, organize guests, estimate a budget, check weather, and check public holidays.

## Problem and users

Planning an event means keeping dates, places, guests, and costs together. EventMate gives users one chat interface for these common planning steps. It is designed for people planning birthdays, parties, and university events.

## Tools and APIs

The assistant has Python tools to create events, add guests, list saved plans, estimate a budget, and cancel an event. It also calls two real public services. Open-Meteo provides weather data, and Nager.Date provides public holiday dates. These services help users choose a suitable date and decide whether an outdoor plan needs a backup.

## LangGraph in simple words

LangGraph is the flow controller. The `assistant` node asks the language model what to do. If the model requests a tool, the graph moves to the `tools` node. The tool result goes back to the assistant, which explains the result to the user. The graph can repeat this process until it has a final answer.

## Conversation memory

The graph stores messages with `InMemorySaver`. Each browser session or terminal run has its own `thread_id`. If I create an event and then ask to list my events, the same thread lets the assistant access that earlier event. The data is temporary and disappears when the app process restarts.

## Approval workflow

Canceling an event can remove saved data, so the tool calls LangGraph's `interrupt()` before it removes anything. The graph pauses and shows the event name and date. If the user approves, the app resumes with `Command(resume=True)`. If the user rejects, it resumes with `Command(resume=False)`, and the event remains saved.

## Live demonstration script

1. Say: “I will create a small outdoor birthday plan in Tbilisi.”
2. Ask: “Create a birthday event for 5 December 2026 in Tbilisi, outdoor, with a budget of 250 GEL.”
3. Note the event ID and ask: “Add Mariam to that event.”
4. Ask: “Check the weather for Tbilisi on 5 December 2026.” If the date is outside the forecast window, explain that the tool reports the limit instead of making up a forecast.
5. Ask: “Check public holidays in Georgia in 2026.”
6. Ask to cancel the event. Show the pause and reject it first. List the events and show it remains.
7. Ask to cancel again and approve. List events and show it was removed.
8. Show the graph diagram and the evaluation table. Explain which tests were run and which still need a live Colab/Groq run.

## Testing results

The project includes automated checks for graph/tool wiring, event memory, external response parsing, approval, rejection, and session isolation. Those tests use a scripted model and mocked HTTP responses, so they do not prove that Groq or public APIs were reached. The notebook has live cells for those checks. After running them, replace `NOT RUN` in the evaluation table with the actual result and a short note.

## Limitations and next steps

The event data is temporary. Weather forecasts do not cover every future date, public holiday coverage can differ by country, and the model may occasionally choose the wrong tool. Later, I could add permanent database storage, user accounts, calendar integration, and a way to edit an event.

## Likely lecturer questions

**What is a tool?**  
A tool is a Python function that the model can call for a specific action, such as saving an event or retrieving weather.

**What does StateGraph do?**  
It defines the graph's steps and the routes between them. Here it sends tool requests to the tools node and returns the results to the assistant.

**How does memory work?**  
`InMemorySaver` stores the graph state for a `thread_id`. Reusing that ID continues the same conversation.

**Why use an interruption before cancellation?**  
It pauses the graph before the destructive action. The user chooses whether it continues.

**What happens if the user rejects cancellation?**  
The graph resumes with a false decision. The tool returns a cancelled-by-user result and keeps the event.

**Are the weather and holiday results real?**  
The tools send HTTP requests to Open-Meteo and Nager.Date. In the live demo, I can show the result and the source name. Unit tests use mocked responses only to test parsing.

**What are the main limitations?**  
The data is temporary, the weather forecast has a limited date range, and model tool selection can make mistakes. The user should check important event details.
