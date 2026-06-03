"""Streamlit web view (#6): streaming (#8) + multi-turn memory (#9) + an inline
**decision trace** that shows how the LangGraph router decided and the Pydantic
structured outputs it produced along the way.

Run:  streamlit run app_web.py
"""
import sys

sys.path.insert(0, "src")

import os  # noqa: E402

import streamlit as st  # noqa: E402
from langchain_core.messages import AIMessageChunk  # noqa: E402

from fitness_agents.hub import build_hub  # noqa: E402
from fitness_agents.observability import capture  # noqa: E402
from fitness_agents.tracing import langfuse_enabled, run_config  # noqa: E402
from fitness_agents.utils import extract_text  # noqa: E402

st.set_page_config(page_title="Fitness Multi-Agent", page_icon="🏋️", layout="centered")
st.title("🏋️ Fitness Coaching Multi-Agent")
st.caption("LangGraph hub → router → {coach · workout generator · workout logger}")
if langfuse_enabled():
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3567")
    st.caption(f"🔭 Langfuse tracing enabled — [open dashboard]({host})")


@st.cache_resource
def get_hub():
    return build_hub(with_memory=True)


hub = get_hub()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "web-" + str(id(st.session_state))
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: {role, route, text, trace}

cfg = run_config(st.session_state.thread_id)
state_cfg = {"configurable": {"thread_id": st.session_state.thread_id}}

ROUTE_BLURB = {
    "COACH": "fitness Q&A — answered directly by the coach sub-graph",
    "WORKOUT_GENERATE": "tool-calling agent: search_exercises → build_workout",
    "WORKOUT_LOG": "parse (structured output) → fuzzy match against the dataset",
    "CLARIFY": "confidence below threshold → ask instead of guessing",
}


def render_trace(trace: dict) -> None:
    """Show how the decision was made: the LangGraph path, the Pydantic
    RouterDecision, the tool calls, and the structured outputs."""
    if not trace:
        return
    route = trace.get("route", "?")
    conf = trace.get("confidence")
    with st.expander("🔍 Decision trace — how this was routed (LangGraph + Pydantic)"):
        # 1. Routing decision (Pydantic RouterDecision)
        st.markdown("**1 · Routing decision** &nbsp; `RouterDecision` (LLM structured output)")
        if conf is not None:
            st.progress(min(max(conf, 0.0), 1.0), text=f"confidence {conf:.2f}  ·  threshold 0.60")
        st.json({
            "route": route,
            "confidence": conf,
            "reasoning": trace.get("reasoning", ""),
        })

        # 2. LangGraph path
        st.markdown("**2 · LangGraph path**")
        path = " → ".join(["START", "router", f"**{route}**"] + trace.get("tool_path", []) + ["END"])
        st.markdown(path)
        st.caption(ROUTE_BLURB.get(route, ""))

        # 3. Tool calls (Pydantic-validated inputs/outputs)
        tool_calls = [e for e in trace.get("events", []) if e.get("event") == "tool_call"]
        if tool_calls:
            st.markdown("**3 · Tool calls** &nbsp; (Pydantic-validated args)")
            for e in tool_calls:
                args = {k: v for k, v in e.items() if k != "event"}
                st.code(f"{args.pop('name', 'tool')}({args})", language="python")

        # 4. Structured output (Pydantic models)
        parsed = next((e for e in trace.get("events", []) if e.get("event") == "parsed_log"), None)
        if parsed:
            st.markdown("**4 · Parsed fields** &nbsp; `ParsedLog` (structured output)")
            st.json({k: v for k, v in parsed.items() if k != "event"})
        entry = next((e for e in trace.get("events", []) if e.get("event") == "structured_log"), None)
        if entry:
            st.markdown("**5 · Structured log entry** &nbsp; `LogEntry` (Pydantic → JSON)")
            st.json({k: v for k, v in entry.items() if k != "event"})

        if langfuse_enabled():
            host = os.environ.get("LANGFUSE_HOST", "http://localhost:3567")
            st.caption(f"Full call-tree trace in Langfuse → {host}/project/fitness-multi-agent/traces")


# --- replay prior turns ---
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        if msg.get("route"):
            st.caption(f"routed → {msg['route']}")
        st.markdown(msg["text"])
        if msg["role"] == "assistant":
            render_trace(msg.get("trace"))


prompt = st.chat_input("Ask a question, request a workout, or log one…")
if prompt:
    st.session_state.history.append({"role": "user", "route": None, "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        route_box = st.empty()
        body = st.empty()
        streamed = ""
        tool_path: list[str] = []
        # Capture every log_event emitted during this turn for the trace panel.
        with capture() as events:
            for _ns, (chunk, meta) in hub.stream(
                {"user_input": prompt, "messages": []},
                cfg,
                stream_mode="messages",
                subgraphs=True,
            ):
                node = meta.get("langgraph_node", "")
                if node in ("tools", "agent") and node not in tool_path:
                    tool_path.append(node)
                if node == "router":
                    continue
                if isinstance(chunk, AIMessageChunk):
                    streamed += extract_text(chunk.content)
                    if streamed:
                        body.markdown(streamed)

        state = hub.get_state(state_cfg).values
        decision = state.get("decision")
        route = decision.route if decision else "?"
        route_box.caption(f"routed → {route}")
        final = streamed or state.get("response", "")
        body.markdown(final)

        trace = {
            "route": route,
            "confidence": decision.confidence if decision else None,
            "reasoning": decision.reasoning if decision else "",
            "events": list(events),
            "tool_path": tool_path,
        }
        render_trace(trace)
        st.session_state.history.append(
            {"role": "assistant", "route": route, "text": final, "trace": trace}
        )
