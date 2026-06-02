"""Hub graph (req #1: StateGraph w/ typed state + explicit edges; req #2: sub-agents
composed as separate compiled graphs).

Flow:  START -> router -> (conditional edge on decision.route) ->
       {coach | generator | logger | clarify} -> END

Multi-turn memory (#9) via a MemorySaver checkpointer keyed by thread_id.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents.coach import build_coach
from .agents.generator import build_generator
from .agents.logger import build_logger
from .observability import log_event
from .router import route
from .state import HubState

_CLARIFY_TEXT = (
    "I'm not sure what you'd like me to do. Are you asking a fitness question, "
    "want me to build a workout, or logging a workout you completed? A little "
    "more detail will help me route this correctly."
)


def _router_node(state: HubState) -> dict:
    user_input = state.get("user_input", "")
    history = state.get("messages", [])
    decision = route(user_input, history=history)
    # Record the user turn into history exactly once.
    return {"decision": decision, "messages": [HumanMessage(content=user_input)]}


def _clarify_node(state: HubState) -> dict:
    decision = state.get("decision")
    text = _CLARIFY_TEXT
    if decision and decision.reasoning:
        log_event("clarify", reasoning=decision.reasoning)
    return {"response": text, "messages": [AIMessage(content=text)]}


def _select_route(state: HubState) -> str:
    decision = state.get("decision")
    return decision.route if decision else "CLARIFY"


def build_hub(with_memory: bool = True):
    coach = build_coach()
    generator = build_generator()
    logger = build_logger()

    g = StateGraph(HubState)
    g.add_node("router", _router_node)
    g.add_node("COACH", coach)
    g.add_node("WORKOUT_GENERATE", generator)
    g.add_node("WORKOUT_LOG", logger)
    g.add_node("CLARIFY", _clarify_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        _select_route,
        {
            "COACH": "COACH",
            "WORKOUT_GENERATE": "WORKOUT_GENERATE",
            "WORKOUT_LOG": "WORKOUT_LOG",
            "CLARIFY": "CLARIFY",
        },
    )
    for node in ("COACH", "WORKOUT_GENERATE", "WORKOUT_LOG", "CLARIFY"):
        g.add_edge(node, END)

    checkpointer = MemorySaver() if with_memory else None
    return g.compile(checkpointer=checkpointer)
