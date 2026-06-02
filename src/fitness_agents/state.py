"""Typed state for the hub graph (req #1: typed state).

`messages` carries multi-turn history (#9, via the add_messages reducer).
`decision` is the router's structured output. `response` is the final text the
hub returns for the turn.
"""
from __future__ import annotations

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages

from .schemas import RouterDecision


class HubState(TypedDict, total=False):
    # Conversation history, accumulated across turns via the add_messages reducer.
    messages: Annotated[list, add_messages]
    # The user's input for the current turn.
    user_input: str
    # The router's structured decision for the current turn.
    decision: Optional[RouterDecision]
    # The final response text produced by the dispatched sub-agent / clarify node.
    response: str
