"""Coach sub-agent (req #2: a separate compiled StateGraph).

Answers general fitness / exercise questions. Multi-turn aware via `messages`.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from ..llm import get_agent_llm
from ..state import HubState
from ..utils import extract_text

_SYSTEM = """You are a knowledgeable, concise fitness coach. Answer the user's \
question accurately and practically. If a question is about specific exercise \
mechanics, explain muscles worked, movement pattern, and key form cues. Keep \
answers focused (a few sentences to a short list)."""


def _coach_node(state: HubState) -> dict:
    llm = get_agent_llm()
    history = state.get("messages", [])
    user_input = state.get("user_input", "")
    messages = [SystemMessage(content=_SYSTEM), *history]
    if user_input and not (history and isinstance(history[-1], HumanMessage)
                           and history[-1].content == user_input):
        messages.append(HumanMessage(content=user_input))
    reply = llm.invoke(messages)
    text = extract_text(reply.content)
    return {"response": text, "messages": [AIMessage(content=text)]}


def build_coach():
    g = StateGraph(HubState)
    g.add_node("coach", _coach_node)
    g.add_edge(START, "coach")
    g.add_edge("coach", END)
    return g.compile()
