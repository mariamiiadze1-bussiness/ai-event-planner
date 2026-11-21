"""Automated checks for EventMate. External HTTP tests use response fixtures."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from agent import EventStore, build_graph, new_thread_config, pending_interrupt


class ScriptedModel:
    """Tiny deterministic model used only to test graph/tool wiring without Groq."""

    def bind_tools(self, tools):
        self.available_tools = {item.name for item in tools}
        return self

    def invoke(self, messages):
        latest = messages[-1]
        if isinstance(latest, HumanMessage):
            text = latest.content.lower()
            if "create" in text or "birthday" in text:
                name = "create_event"
                args = {"name": "Birthday", "event_date": "2026-12-05", "city": "Tbilisi", "venue_type": "outdoor", "budget": 250, "currency": "GEL"}
            elif "weather" in text:
                name, args = "get_weather", {"city": "Tbilisi", "event_date": "2026-12-05"}
            elif "holiday" in text:
                name, args = "get_public_holidays", {"country_code": "GE", "year": 2026}
            elif "cancel" in text:
                name, args = "cancel_event", {"event_id": "evt-1"}
            elif "guest" in text:
                name, args = "add_guest", {"event_id": "evt-1", "name": "Mariam", "email": ""}
            else:
                name, args = "list_events", {}
            return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "call-1", "type": "tool_call"}])
        if isinstance(latest, ToolMessage):
            return AIMessage(content=f"Tool result received: {latest.content}")
        return AIMessage(content="Test response")


class EventPlannerTests(unittest.TestCase):
    def setUp(self):
        self.store = EventStore()
        self.model = ScriptedModel()
        self.graph = build_graph(event_store=self.store, model=self.model)
        self.config = new_thread_config("test-thread")

    def test_add_event_with_agent_tool(self):
        result = self.graph.invoke({"messages": [HumanMessage(content="Create a birthday event")]}, self.config)
        self.assertIn("Birthday", result["messages"][-1].content)
        self.assertEqual(len(self.store.list_events("test-thread")), 1)

    def test_retrieve_previously_added_event(self):
        self.store.create_event("test-thread", {"event_id": "evt-1", "name": "Birthday", "date": "2026-12-05", "city": "Tbilisi", "venue_type": "outdoor", "budget": 250, "currency": "GEL", "guests": []})
        result = self.graph.invoke({"messages": [HumanMessage(content="List my events")]}, self.config)
        self.assertIn("Birthday", result["messages"][-1].content)

    def test_add_guest_to_event(self):
        self.store.create_event("test-thread", {"event_id": "evt-1", "name": "Birthday", "date": "2026-12-05", "city": "Tbilisi", "venue_type": "outdoor", "budget": 250, "currency": "GEL", "guests": []})
        add_guest = next(tool for tool in __import__("agent").create_tools(self.store) if tool.name == "add_guest")
        result = add_guest.invoke({"event_id": "evt-1", "name": "Mariam", "email": "mariam@example.com"}, config=self.config)
        self.assertEqual(result["guest"]["name"], "Mariam")
        self.assertEqual(self.store.get_event("test-thread", "evt-1")["guests"][0]["email"], "mariam@example.com")

    def test_budget_estimate(self):
        budget = next(tool for tool in __import__("agent").create_tools(self.store) if tool.name == "calculate_budget")
        result = budget.invoke({"total_budget": 300, "guest_count": 10, "categories": "food,venue,decor"})
        self.assertEqual(result["per_guest_budget"], 30.0)
        self.assertEqual(result["category_estimates"], {"food": 100.0, "venue": 100.0, "decor": 100.0})

    @patch("agent.requests.get")
    def test_weather_tool_parses_open_meteo_response(self, get):
        geocode = Mock()
        geocode.json.return_value = {"results": [{"name": "Tbilisi", "country": "Georgia", "latitude": 41.7, "longitude": 44.8}]}
        geocode.raise_for_status.return_value = None
        forecast = Mock()
        forecast.json.return_value = {"daily": {"time": ["2026-12-05"], "temperature_2m_max": [12.0], "precipitation_probability_max": [20], "weather_code": [2]}}
        forecast.raise_for_status.return_value = None
        get.side_effect = [geocode, forecast]
        weather_tool = next(tool for tool in __import__("agent").create_tools(self.store) if tool.name == "get_weather")
        result = weather_tool.invoke({"city": "Tbilisi", "event_date": "2026-12-05"})
        self.assertEqual(result["temperature_max_c"], 12.0)
        self.assertEqual(get.call_count, 2)

    @patch("agent.requests.get")
    def test_holiday_tool_parses_nager_response(self, get):
        response = Mock()
        response.json.return_value = [{"date": "2026-01-01", "localName": "New Year", "name": "New Year's Day"}]
        response.raise_for_status.return_value = None
        get.return_value = response
        holiday_tool = next(tool for tool in __import__("agent").create_tools(self.store) if tool.name == "get_public_holidays")
        result = holiday_tool.invoke({"country_code": "GE", "year": 2026})
        self.assertEqual(result[0]["name"], "New Year")

    def test_approval_cancels_event(self):
        self.store.create_event("test-thread", {"event_id": "evt-1", "name": "Birthday", "date": "2026-12-05", "city": "Tbilisi", "venue_type": "outdoor", "budget": 250, "currency": "GEL", "guests": []})
        paused = self.graph.invoke({"messages": [HumanMessage(content="Cancel this event")]}, self.config)
        self.assertIsNotNone(pending_interrupt(paused))
        finished = self.graph.invoke(Command(resume=True), self.config)
        self.assertEqual(self.store.list_events("test-thread"), [])
        self.assertIn("event_cancelled", finished["messages"][-1].content)

    def test_rejection_keeps_event(self):
        self.store.create_event("test-thread", {"event_id": "evt-1", "name": "Birthday", "date": "2026-12-05", "city": "Tbilisi", "venue_type": "outdoor", "budget": 250, "currency": "GEL", "guests": []})
        paused = self.graph.invoke({"messages": [HumanMessage(content="Cancel this event")]}, self.config)
        self.assertIsNotNone(pending_interrupt(paused))
        self.graph.invoke(Command(resume=False), self.config)
        self.assertEqual(len(self.store.list_events("test-thread")), 1)

    def test_event_data_is_isolated_by_thread(self):
        self.store.create_event("one", {"event_id": "evt-1", "name": "Private party", "date": "2026-12-05", "city": "Tbilisi", "venue_type": "indoor", "budget": 0, "currency": "GEL", "guests": []})
        self.assertEqual(len(self.store.list_events("one")), 1)
        self.assertEqual(self.store.list_events("two"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
