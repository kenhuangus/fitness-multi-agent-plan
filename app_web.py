"""Minimal Streamlit web view (#6) showcasing streaming (#8) + multi-turn memory (#9).

Run:  streamlit run app_web.py
"""
import sys

sys.path.insert(0, "src")

import streamlit as st  # noqa: E402
from langchain_core.messages import AIMessageChunk  # noqa: E402

from fitness_agents.hub import build_hub  # noqa: E402
from fitness_agents.tracing import langfuse_enabled, run_config  # noqa: E402
from fitness_agents.utils import extract_text  # noqa: E402

st.set_page_config(page_title="Fitness Multi-Agent", page_icon="🏋️")
st.title("🏋️ Fitness Coaching Multi-Agent")
st.caption("LangGraph hub → router → {coach · workout generator · workout logger}")
if langfuse_enabled():
    st.caption("🔭 Langfuse tracing enabled")


@st.cache_resource
def get_hub():
    return build_hub(with_memory=True)


hub = get_hub()
# One persistent thread per browser session -> multi-turn memory.
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "web-" + str(id(st.session_state))
if "history" not in st.session_state:
    st.session_state.history = []  # list of (role, route, text)

cfg = run_config(st.session_state.thread_id)
state_cfg = {"configurable": {"thread_id": st.session_state.thread_id}}

for role, route, text in st.session_state.history:
    with st.chat_message(role):
        if route:
            st.caption(f"routed → {route}")
        st.markdown(text)

prompt = st.chat_input("Ask a question, request a workout, or log one…")
if prompt:
    st.session_state.history.append(("user", None, prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        route_box = st.empty()
        body = st.empty()
        streamed = ""
        for _ns, (chunk, meta) in hub.stream(
            {"user_input": prompt, "messages": []},
            cfg,
            stream_mode="messages",
            subgraphs=True,
        ):
            if meta.get("langgraph_node") == "router":
                continue
            if isinstance(chunk, AIMessageChunk):
                streamed += extract_text(chunk.content)
                if streamed:
                    body.markdown(streamed)

        state = hub.get_state(state_cfg).values
        route = state["decision"].route if state.get("decision") else "?"
        route_box.caption(f"routed → {route}")
        final = streamed or state.get("response", "")
        body.markdown(final)
        st.session_state.history.append(("assistant", route, final))
