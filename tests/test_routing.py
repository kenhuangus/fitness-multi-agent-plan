"""Critical path #1 — routing correctness, especially the low-confidence guard.

Why this path: the router is the single point that can silently send a request to
the wrong sub-agent. Misrouting is the highest-leverage correctness failure in the
system, and the spec explicitly requires that ambiguous/low-confidence inputs are
not silently misrouted. We test the *policy* deterministically (mocking the LLM) so
the test is fast and not flaky: a high-confidence decision passes through, a
low-confidence decision is downgraded to CLARIFY, and an LLM error falls back to
CLARIFY.
"""
import fitness_agents.router as router_mod
from fitness_agents.schemas import RouterDecision


class _FakeStructured:
    """Stand-in for llm.with_structured_output(RouterDecision)."""

    def __init__(self, decision=None, raise_exc=None):
        self._decision = decision
        self._raise = raise_exc

    def invoke(self, _messages):
        if self._raise:
            raise self._raise
        return self._decision


class _FakeLLM:
    def __init__(self, fake):
        self._fake = fake

    def with_structured_output(self, _schema):
        return self._fake


def _patch_router(monkeypatch, decision=None, raise_exc=None):
    fake = _FakeLLM(_FakeStructured(decision, raise_exc))
    monkeypatch.setattr(router_mod, "get_router_llm", lambda: fake)


def test_high_confidence_passes_through(monkeypatch):
    decision = RouterDecision(route="COACH", confidence=0.95, reasoning="clear question")
    _patch_router(monkeypatch, decision=decision)
    result = router_mod.route("What muscles does a deadlift work?")
    assert result.route == "COACH"
    assert result.confidence == 0.95


def test_low_confidence_downgrades_to_clarify(monkeypatch):
    # Model picked a route but with confidence below threshold (0.6) -> must CLARIFY.
    decision = RouterDecision(route="WORKOUT_GENERATE", confidence=0.4, reasoning="unsure")
    _patch_router(monkeypatch, decision=decision)
    result = router_mod.route("Bench press")
    assert result.route == "CLARIFY", "low-confidence input must not be silently routed"


def test_explicit_clarify_is_respected(monkeypatch):
    decision = RouterDecision(route="CLARIFY", confidence=0.2, reasoning="ambiguous")
    _patch_router(monkeypatch, decision=decision)
    assert router_mod.route("I did a workout yesterday, can you adjust it?").route == "CLARIFY"


def test_llm_error_falls_back_to_clarify(monkeypatch):
    _patch_router(monkeypatch, raise_exc=RuntimeError("provider down"))
    result = router_mod.route("anything")
    assert result.route == "CLARIFY"
    assert result.confidence == 0.0
