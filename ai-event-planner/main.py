"""Interactive command-line chat for EventMate."""

from __future__ import annotations

import getpass
import os

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from agent import EventStore, build_graph, latest_assistant_text, new_thread_config, pending_interrupt


def ensure_api_key() -> None:
    if not os.environ.get("GROQ_API_KEY", "").strip():
        try:
            os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key (input hidden): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNo API key entered. Exiting.")
            raise SystemExit(1)
    if not os.environ["GROQ_API_KEY"]:
        print("GROQ_API_KEY cannot be empty.")
        raise SystemExit(1)


def main() -> None:
    ensure_api_key()
    graph = build_graph(event_store=EventStore())
    config = new_thread_config()
    print("EventMate is ready. Type 'exit' to end the conversation.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if query.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            break
        if not query:
            continue

        try:
            result = graph.invoke({"messages": [HumanMessage(content=query)]}, config)
            interruption = pending_interrupt(result)
            if interruption:
                print(f"\nAPPROVAL REQUIRED: {interruption.get('message', 'Confirm this action?')}")
                answer = input("Approve? [y/N]: ").strip().lower()
                approved = answer in {"y", "yes"}
                result = graph.invoke(Command(resume=approved), config)
            print(f"\nEventMate: {latest_assistant_text(result)}\n")
        except Exception as exc:
            print(f"\nEventMate encountered {type(exc).__name__}. Check the API key or connection and try again.\n")


if __name__ == "__main__":
    main()
