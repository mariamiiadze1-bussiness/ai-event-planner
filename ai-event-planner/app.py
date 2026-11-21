"""Streamlit chat interface for EventMate."""

from __future__ import annotations

import os

import streamlit as st
from langgraph.types import Command

from agent import EventStore, build_graph, latest_assistant_text, new_thread_config, pending_interrupt


@st.cache_resource
def get_agent_bundle():
    """Create one graph per Streamlit process; each browser gets its own thread ID."""
    store = EventStore()
    return build_graph(event_store=store), store


def set_api_key() -> bool:
    """Read the Groq key from Streamlit Secrets or the host environment."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        try:
            key = str(st.secrets.get("GROQ_API_KEY", "")).strip()
        except Exception:
            key = ""
    if key:
        os.environ["GROQ_API_KEY"] = key
        return True
    st.error("GROQ_API_KEY is missing. Add it to Streamlit Secrets or set it in your environment.")
    st.code('GROQ_API_KEY = "your_key_here"')
    return False


def render_history() -> None:
    for message in st.session_state.history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def resume_approval(graph, config, approved: bool) -> None:
    """Resume the pending LangGraph interrupt with the user's button choice."""
    with st.spinner("Continuing the event plan..."):
        result = graph.invoke(Command(resume=approved), config=config)
    st.session_state.history.append({"role": "assistant", "content": latest_assistant_text(result)})
    st.session_state.pending = pending_interrupt(result)


def main() -> None:
    st.set_page_config(page_title="EventMate | AI Event Planner", page_icon="🎉", layout="wide")
    st.title("🎉 EventMate")
    st.caption("An AI event planner for birthdays, parties, and university events.")

    if not set_api_key():
        st.stop()

    graph, store = get_agent_bundle()
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = new_thread_config()["configurable"]["thread_id"]
        st.session_state.config = new_thread_config(st.session_state.thread_id)
        st.session_state.history = []
        st.session_state.pending = None

    with st.sidebar:
        st.subheader("Your event plans")
        events = store.list_events(st.session_state.thread_id)
        if not events:
            st.write("No events saved in this session yet.")
        for event in events:
            st.markdown(f"**{event['name']}**  \n{event['date']} · {event['city']} · {event['venue_type']}")
            st.caption(f"ID: {event['event_id']} · {len(event['guests'])} guest(s) · {event['budget']} {event['currency']}")
        if st.button("Start a new conversation", use_container_width=True):
            st.session_state.thread_id = new_thread_config()["configurable"]["thread_id"]
            st.session_state.config = new_thread_config(st.session_state.thread_id)
            st.session_state.history = []
            st.session_state.pending = None
            st.rerun()

    render_history()

    if st.session_state.pending:
        interrupt_info = st.session_state.pending
        st.warning(interrupt_info.get("message", "The agent is waiting for your decision."))
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Approve cancellation", type="primary", use_container_width=True):
                resume_approval(graph, st.session_state.config, True)
                st.rerun()
        with col_no:
            if st.button("Keep event", use_container_width=True):
                resume_approval(graph, st.session_state.config, False)
                st.rerun()
    else:
        prompt = st.chat_input("Tell EventMate what you are planning...")
        if prompt:
            st.session_state.history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            try:
                with st.chat_message("assistant"):
                    with st.spinner("Planning with EventMate..."):
                        result = graph.invoke({"messages": [{"role": "user", "content": prompt}]}, st.session_state.config)
                    interrupted = pending_interrupt(result)
                    if interrupted:
                        st.session_state.pending = interrupted
                        st.warning(interrupted.get("message", "The agent is waiting for your decision."))
                    else:
                        response = latest_assistant_text(result)
                        st.markdown(response)
                        st.session_state.history.append({"role": "assistant", "content": response})
            except Exception as exc:
                message = f"I could not complete that request ({type(exc).__name__}). Check your API key and try again."
                st.error(message)
                st.session_state.history.append({"role": "assistant", "content": message})
            st.rerun()


if __name__ == "__main__":
    main()
