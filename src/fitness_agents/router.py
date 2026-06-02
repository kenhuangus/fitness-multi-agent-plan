"""Router (req #4): classifies intent via LLM structured output (no regex/keywords).

Low-confidence policy (explicit design decision): if the model's confidence is
below CONFIDENCE_THRESHOLD, we route to CLARIFY instead of guessing — the hub then
asks the user to clarify. This guarantees the system never silently misroutes.
Any error producing the structured decision also falls back to CLARIFY.
"""
from __future__ import annotations

import os

from langchain_core.messages import HumanMessage, SystemMessage

from .llm import get_router_llm
from .observability import log_event
from .schemas import RouterDecision

CONFIDENCE_THRESHOLD = float(os.environ.get("ROUTER_CONFIDENCE_THRESHOLD", "0.6"))

_SYSTEM = """You are the router for a fitness coaching assistant. Classify the \
user's latest message into exactly one route and report your confidence.

Routes:
- COACH: general fitness or exercise questions ("What muscles does a deadlift work?").
- WORKOUT_GENERATE: requests to build/design/plan a workout ("Build me a 30 min upper body session").
- WORKOUT_LOG: the user reporting a completed workout to record ("I did 3x10 bench at 185 lbs").
- CLARIFY: the intent is ambiguous or underspecified ("Bench press"; "I did a workout yesterday, can you adjust it?").

An explicit request to build/create/design/give a workout is WORKOUT_GENERATE with \
HIGH confidence — even when it also mentions an injury, available equipment, or a \
time limit. Those are *constraints for the generator*, not signs of ambiguity (e.g. \
"My shoulder is injured, give me a 15 min dumbbell workout" is a confident \
WORKOUT_GENERATE). Likewise an explicit "log this" / past-tense report with an \
exercise and numbers is a confident WORKOUT_LOG.

Set confidence in [0,1]. Use a LOW confidence (< 0.6) only when the message is \
genuinely vague, could fit multiple routes, or lacks the detail needed to act (e.g. \
a bare exercise name, or "adjust my workout" with no prior context). Prefer CLARIFY \
over guessing when genuinely unsure. Consider the prior conversation for context."""


def route(user_input: str, history: list | None = None) -> RouterDecision:
    """Return a RouterDecision. Applies the low-confidence -> CLARIFY policy."""
    llm = get_router_llm().with_structured_output(RouterDecision)
    messages = [SystemMessage(content=_SYSTEM)]
    if history:
        messages.extend(history[-6:])  # recent context for ambiguity resolution
    messages.append(HumanMessage(content=user_input))

    try:
        decision: RouterDecision = llm.invoke(messages)
    except Exception as exc:  # noqa: BLE001 - resilience: never crash on routing
        log_event("route_error", error=repr(exc))
        return RouterDecision(
            route="CLARIFY",
            confidence=0.0,
            reasoning=f"Router error, defaulting to clarify: {exc!r}",
        )

    # Low-confidence policy: downgrade to CLARIFY rather than risk a misroute.
    if decision.route != "CLARIFY" and decision.confidence < CONFIDENCE_THRESHOLD:
        log_event(
            "route_decision",
            route="CLARIFY",
            original_route=decision.route,
            confidence=decision.confidence,
            downgraded=True,
            reasoning=decision.reasoning,
        )
        return RouterDecision(
            route="CLARIFY",
            confidence=decision.confidence,
            reasoning=(
                f"Low confidence ({decision.confidence:.2f}) for "
                f"{decision.route}: {decision.reasoning}"
            ),
        )

    log_event(
        "route_decision",
        route=decision.route,
        confidence=decision.confidence,
        downgraded=False,
        reasoning=decision.reasoning,
    )
    return decision
