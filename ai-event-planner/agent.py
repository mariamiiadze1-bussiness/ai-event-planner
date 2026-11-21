"""AI Event Planner: a beginner-friendly LangGraph assistant.

Events and guests are held in memory and isolated by LangGraph thread ID. The
checkpointer also keeps conversation history and pauses safely before canceling.
"""

from __future__ import annotations

import os
import json
import threading
import uuid
from datetime import date
from typing import Any, Annotated, TypedDict

import requests
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

DEFAULT_MODEL = "openai/gpt-oss-20b"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
NAGER_HOLIDAYS_URL = "https://date.nager.at/api/v3/PublicHolidays"
REQUEST_TIMEOUT = 15


class AgentState(TypedDict):
    """Graph state: messages are accumulated to preserve conversation history."""

    messages: Annotated[list[AnyMessage], add_messages]


class EventStore:
    """Small thread-safe memory store, partitioned by conversation thread ID."""

    def __init__(self) -> None:
        self._events: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def list_events(self, thread_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item, guests=list(item["guests"])) for item in self._events.get(thread_id, {}).values()]

    def create_event(self, thread_id: str, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._events.setdefault(thread_id, {})[event["event_id"]] = event
            return dict(event, guests=list(event["guests"]))

    def add_guest(self, thread_id: str, event_id: str, guest: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            event = self._events.get(thread_id, {}).get(event_id)
            if event is None:
                return None
            event["guests"].append(guest)
            return dict(guest)

    def get_event(self, thread_id: str, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            event = self._events.get(thread_id, {}).get(event_id)
            return dict(event, guests=list(event["guests"])) if event else None

    def cancel_event(self, thread_id: str, event_id: str) -> bool:
        with self._lock:
            events = self._events.get(thread_id, {})
            return events.pop(event_id, None) is not None


def _thread_id(config: RunnableConfig | None) -> str:
    """Read the isolated conversation ID supplied by LangGraph."""
    configurable = (config or {}).get("configurable", {})
    return str(configurable.get("thread_id", "default"))


def _parse_event_date(value: str) -> date:
    """Validate an ISO date and return a useful error for the model/user."""
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Use a valid date in YYYY-MM-DD format.") from exc


def create_tools(store: EventStore) -> list[Any]:
    """Create LangChain tools that all use the same session-isolated store."""

    @tool
    def create_event(
        name: str,
        event_date: str,
        city: str,
        venue_type: str = "indoor",
        budget: float = 0,
        currency: str = "USD",
        *,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """Create an event plan with its date, city, venue type, and budget."""
        if not name.strip() or not city.strip():
            raise ValueError("Event name and city must not be empty.")
        parsed_date = _parse_event_date(event_date)
        if budget < 0:
            raise ValueError("Budget must be zero or more.")
        normalized_venue = venue_type.strip().lower()
        if normalized_venue not in {"indoor", "outdoor"}:
            raise ValueError("venue_type must be 'indoor' or 'outdoor'.")
        event = {
            "event_id": str(uuid.uuid4())[:8],
            "name": name.strip(),
            "date": parsed_date.isoformat(),
            "city": city.strip(),
            "venue_type": normalized_venue,
            "budget": round(float(budget), 2),
            "currency": currency.strip().upper() or "USD",
            "guests": [],
        }
        return store.create_event(_thread_id(config), event)

    @tool
    def add_guest(
        event_id: str,
        name: str,
        email: str = "",
        *,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        """Add a named guest to an existing event using its event ID."""
        if not name.strip():
            raise ValueError("Guest name must not be empty.")
        guest = {"name": name.strip(), "email": email.strip()}
        result = store.add_guest(_thread_id(config), event_id.strip(), guest)
        if result is None:
            return {"error": f"No event found with ID {event_id!r} in this conversation."}
        return {"event_id": event_id, "guest": result}

    @tool
    def list_events(config: RunnableConfig) -> list[dict[str, Any]]:
        """List this conversation's events and their guest lists."""
        return store.list_events(_thread_id(config))

    @tool
    def calculate_budget(total_budget: float, guest_count: int, categories: str = "food,decorations,venue") -> dict[str, Any]:
        """Split an event budget evenly across comma-separated spending categories."""
        if total_budget < 0 or guest_count < 0:
            raise ValueError("Budget and guest count must not be negative.")
        names = [part.strip() for part in categories.split(",") if part.strip()]
        if not names:
            raise ValueError("Provide at least one budget category.")
        each = round(float(total_budget) / len(names), 2)
        return {
            "total_budget": round(float(total_budget), 2),
            "guest_count": guest_count,
            "per_guest_budget": round(float(total_budget) / guest_count, 2) if guest_count else None,
            "category_estimates": {name: each for name in names},
        }

    @tool
    def get_weather(city: str, event_date: str) -> dict[str, Any]:
        """Get a real Open-Meteo forecast for an outdoor event's city and date."""
        target_date = _parse_event_date(event_date)
        try:
            location_response = requests.get(
                OPEN_METEO_GEOCODING_URL,
                params={"name": city.strip(), "count": 1, "language": "en", "format": "json"},
                timeout=REQUEST_TIMEOUT,
            )
            location_response.raise_for_status()
            locations = location_response.json().get("results", [])
            if not locations:
                return {"error": f"Open-Meteo could not find the city {city!r}."}
            place = locations[0]
            forecast_response = requests.get(
                OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "daily": "temperature_2m_max,precipitation_probability_max,weather_code",
                    "timezone": "auto",
                    "start_date": target_date.isoformat(),
                    "end_date": target_date.isoformat(),
                },
                timeout=REQUEST_TIMEOUT,
            )
            forecast_response.raise_for_status()
            daily = forecast_response.json().get("daily", {})
            if not daily.get("time"):
                return {"error": "Open-Meteo returned no forecast for that date. Forecast dates are limited."}
            return {
                "city": place.get("name", city),
                "country": place.get("country"),
                "date": daily["time"][0],
                "temperature_max_c": daily.get("temperature_2m_max", [None])[0],
                "precipitation_probability_max_percent": daily.get("precipitation_probability_max", [None])[0],
                "weather_code": daily.get("weather_code", [None])[0],
                "source": "Open-Meteo",
            }
        except requests.RequestException as exc:
            return {"error": f"Weather service request failed: {exc.__class__.__name__}. Please try again."}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return {"error": f"Weather service returned unexpected data: {exc.__class__.__name__}."}

    @tool
    def get_public_holidays(country_code: str, year: int) -> list[dict[str, Any]] | dict[str, str]:
        """Look up real public holiday dates for a two-letter country code using Nager.Date."""
        code = country_code.strip().upper()
        if len(code) != 2 or not code.isalpha():
            raise ValueError("Use a two-letter country code, such as GE, US, or GB.")
        if year < 1900 or year > 2100:
            raise ValueError("Year must be between 1900 and 2100.")
        try:
            response = requests.get(f"{NAGER_HOLIDAYS_URL}/{year}/{code}", timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                return {"error": "Holiday service returned an unexpected response."}
            return [{"date": item.get("date"), "name": item.get("localName") or item.get("name")} for item in data]
        except requests.RequestException as exc:
            return {"error": f"Holiday service request failed: {exc.__class__.__name__}. Please try again."}

    @tool
    def cancel_event(event_id: str, config: RunnableConfig) -> dict[str, Any]:
        """Cancel an event only after the human approves the LangGraph interruption."""
        thread_id = _thread_id(config)
        event = store.get_event(thread_id, event_id.strip())
        if event is None:
            return {"error": f"No event found with ID {event_id!r} in this conversation."}
        decision = interrupt(
            {
                "action": "cancel_event",
                "event_id": event["event_id"],
                "event_name": event["name"],
                "event_date": event["date"],
                "message": f"Cancel {event['name']!r} on {event['date']}? Approve or reject this action.",
            }
        )
        approved = decision is True or (isinstance(decision, dict) and decision.get("approved") is True)
        if not approved:
            return {"status": "cancelled_by_user", "event_id": event["event_id"], "event_kept": True}
        removed = store.cancel_event(thread_id, event["event_id"])
        return {"status": "event_cancelled" if removed else "event_not_found", "event_id": event["event_id"]}

    return [create_event, add_guest, list_events, calculate_budget, get_weather, get_public_holidays, cancel_event]


def build_graph(
    *,
    model_name: str | None = None,
    checkpointer: Any | None = None,
    event_store: EventStore | None = None,
    model: Any | None = None,
) -> Any:
    """Build and compile the assistant graph. Pass a fake model only in unit tests."""
    if model is None:
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is missing. Set it in your environment or Colab/Streamlit Secrets.")
        from langchain_groq import ChatGroq

        model = ChatGroq(model=model_name or DEFAULT_MODEL, temperature=0, max_tokens=700, max_retries=2)

    store = event_store or EventStore()
    tools = create_tools(store)
    tools_by_name = {item.name: item for item in tools}
    model_with_tools = model.bind_tools(tools)
    system_message = SystemMessage(
        content=(
            "You are EventMate, a friendly AI Event Planner for students and families. "
            "Plan birthdays, parties, and university events. Ask for missing required details before creating an event. "
            "Use tools for saved event data, real weather, and public holiday lookups. Explain estimates clearly. "
            "Never claim a forecast or holiday lookup succeeded unless its tool returned data. "
            "Before cancel_event, call the tool; it will pause and ask the human for approval. Do not say an event "
            "was cancelled until the tool returns event_cancelled. A rejected request leaves the event saved. "
            "Use the event ID returned by create_event when adding guests or cancelling. Keep replies concise and clear."
        )
    )

    def assistant_node(state: AgentState) -> dict[str, list[AnyMessage]]:
        answer = model_with_tools.invoke([system_message, *state["messages"]])
        return {"messages": [answer]}

    def tools_node(state: AgentState, config: RunnableConfig) -> dict[str, list[AnyMessage]]:
        last = state["messages"][-1]
        tool_messages: list[ToolMessage] = []
        for call in last.tool_calls:
            selected = tools_by_name.get(call["name"])
            if selected is None:
                content: Any = {"error": f"Unknown tool: {call['name']}"}
            else:
                try:
                    content = selected.invoke(call.get("args", {}), config=config)
                except (ValueError, requests.RequestException) as exc:
                    content = {"error": str(exc)}
            tool_messages.append(
                ToolMessage(
                    content=json.dumps(content, ensure_ascii=False, default=str),
                    tool_call_id=call["id"],
                    name=call["name"],
                )
            )
        return {"messages": tool_messages}

    def route_after_assistant(state: AgentState) -> str:
        return "tools" if isinstance(state["messages"][-1], AIMessage) and state["messages"][-1].tool_calls else END

    builder = StateGraph(AgentState)
    builder.add_node("assistant", assistant_node)
    builder.add_node("tools", tools_node)
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", route_after_assistant, {"tools": "tools", END: END})
    builder.add_edge("tools", "assistant")
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


def new_thread_config(thread_id: str | None = None) -> dict[str, Any]:
    """Return a LangGraph config for a new or existing conversation."""
    return {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}


def pending_interrupt(result: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first interrupt payload from an invoke result, when present."""
    interruptions = result.get("__interrupt__", ())
    if interruptions:
        value = getattr(interruptions[0], "value", interruptions[0])
        return value if isinstance(value, dict) else {"message": str(value)}
    return None


def latest_assistant_text(result: dict[str, Any]) -> str:
    """Find the newest human-readable assistant message in a graph result."""
    for message in reversed(result.get("messages", [])):
        if isinstance(message, AIMessage) and isinstance(message.content, str) and message.content.strip():
            return message.content
    return "The agent finished without a text response."


__all__ = [
    "AgentState", "EventStore", "build_graph", "create_tools", "latest_assistant_text",
    "new_thread_config", "pending_interrupt",
]
