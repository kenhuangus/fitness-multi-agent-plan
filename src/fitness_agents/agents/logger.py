"""Workout Logger sub-agent (req #2: separate compiled StateGraph).

Two-node graph:
1. parse   - LLM structured output extracts exercise name, sets, reps, weight.
2. match   - deterministic fuzzy match against the dataset (rapidfuzz).
Returns a structured JSON LogEntry. Low fuzzy score -> unmatched + candidates
(never forces a hallucinated match).
"""
from __future__ import annotations

import os
from typing import Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from .. import data
from ..llm import get_agent_llm
from ..observability import log_event
from ..schemas import LogEntry, ParsedLog
from ..state import HubState

FUZZY_THRESHOLD = float(os.environ.get("LOGGER_FUZZY_THRESHOLD", "70"))

_SYSTEM = """Extract structured workout-log fields from the user's message. \
Capture the exercise name exactly as phrased, plus sets, reps, weight, and unit \
when present. If a field is absent, leave it null."""


class _LogState(HubState, total=False):
    parsed: Optional[ParsedLog]
    log_entry: Optional[dict]


def _parse_node(state: _LogState) -> dict:
    llm = get_agent_llm().with_structured_output(ParsedLog)
    user_input = state.get("user_input", "")
    try:
        parsed: ParsedLog = llm.invoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=user_input)]
        )
    except Exception as exc:  # noqa: BLE001 - resilience
        log_event("logger_parse_error", error=repr(exc))
        parsed = ParsedLog(exercise_name_raw=user_input)
    return {"parsed": parsed}


def _match_node(state: _LogState) -> dict:
    parsed: ParsedLog = state["parsed"]
    matches = data.find_fuzzy(parsed.exercise_name_raw, limit=3)
    best_ex, best_score = matches[0] if matches else (None, 0.0)

    entry = LogEntry(
        exercise_name_raw=parsed.exercise_name_raw,
        sets=parsed.sets,
        reps=parsed.reps,
        weight=parsed.weight,
        unit=parsed.unit,
    )
    if best_ex and best_score >= FUZZY_THRESHOLD:
        entry.matched_exercise_id = best_ex["id"]
        entry.matched_exercise_name = best_ex["name"]
        entry.match_confidence = round(best_score / 100.0, 3)
    else:
        entry.candidates = [e["name"] for e, _ in matches]
        entry.match_confidence = round((best_score or 0.0) / 100.0, 3)

    log_event(
        "tool_call",
        name="fuzzy_match",
        raw=parsed.exercise_name_raw,
        matched=entry.matched_exercise_name,
        score=best_score,
    )

    data_json = entry.model_dump()
    if entry.matched_exercise_name:
        text = (
            f"Logged: {entry.sets or '?'}x{entry.reps or '?'} "
            f"{entry.matched_exercise_name}"
            + (f" @ {entry.weight} {entry.unit or ''}".rstrip() if entry.weight else "")
            + f" (matched '{entry.exercise_name_raw}', "
            f"confidence {entry.match_confidence:.2f}).\n\n```json\n"
            f"{_pretty(data_json)}\n```"
        )
    else:
        cands = ", ".join(entry.candidates) or "no close matches"
        text = (
            f"I couldn't confidently match '{entry.exercise_name_raw}' to the "
            f"exercise dataset. Did you mean: {cands}? Here is the raw entry:\n\n"
            f"```json\n{_pretty(data_json)}\n```"
        )
    return {"response": text, "log_entry": data_json,
            "messages": [AIMessage(content=text)]}


def _pretty(d: dict) -> str:
    import json

    return json.dumps(d, indent=2)


def build_logger():
    g = StateGraph(_LogState)
    g.add_node("parse", _parse_node)
    g.add_node("match", _match_node)
    g.add_edge(START, "parse")
    g.add_edge("parse", "match")
    g.add_edge("match", END)
    return g.compile()
