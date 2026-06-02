"""Workout Generator sub-agent (req #2: separate compiled StateGraph).

A tool-calling agent with search_exercises + build_workout. We compose the
prebuilt ReAct agent (its own compiled graph) inside a thin StateGraph node so it
plugs into the hub's typed state. Resilience: tool errors are surfaced as tool
messages (not exceptions), and a try/except guards the whole turn.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from ..llm import get_agent_llm
from ..observability import log_event
from ..state import HubState
from ..tools import TOOLS
from ..utils import extract_text

_SYSTEM = """You are a workout-building agent. To design a workout:
1. Call search_exercises to find candidate exercises (filter by muscle groups, \
equipment, and movement patterns; pass exclude_joints if the user mentions an injury).
2. If search returns no results, tell the user nothing matched and ask them to \
adjust — never invent exercises.
3. Call build_workout with the chosen exercise IDs (use the real IDs from search \
results only) to assemble warmup/main/cooldown with sets, reps, and rest.
4. Present the final workout clearly. If build_workout reports invalid IDs, fix \
them by re-searching rather than guessing.
Keep total work appropriate to the requested duration."""

# Inner ReAct agent — itself a compiled LangGraph graph. Built lazily so importing
# this module doesn't require an API key (keeps tests that mock the LLM cheap).
_react_agent = None


def _get_react_agent():
    global _react_agent
    if _react_agent is None:
        _react_agent = create_react_agent(get_agent_llm(), TOOLS)
    return _react_agent


def _generator_node(state: HubState) -> dict:
    history = state.get("messages", [])
    user_input = state.get("user_input", "")
    convo = [SystemMessage(content=_SYSTEM), *history]
    if user_input and not (history and isinstance(history[-1], HumanMessage)
                           and history[-1].content == user_input):
        convo.append(HumanMessage(content=user_input))
    try:
        result = _get_react_agent().invoke({"messages": convo})
        text = extract_text(result["messages"][-1].content)
    except Exception as exc:  # noqa: BLE001 - resilience
        log_event("generator_error", error=repr(exc))
        text = (
            "I hit an error while building the workout. Could you restate the "
            "muscle groups, equipment, and target duration?"
        )
    return {"response": text, "messages": [AIMessage(content=text)]}


def build_generator():
    g = StateGraph(HubState)
    g.add_node("generator", _generator_node)
    g.add_edge(START, "generator")
    g.add_edge("generator", END)
    return g.compile()
