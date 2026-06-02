# Implementation Plan — Fitness Coaching Multi-Agent System

> **Authority:** Where the PRD and README/ASSESSMENT conflict, **README/ASSESSMENT wins**.
> In practice they align; the README simply emphasizes *correctness over completeness* and
> *"stub or mock anything not core."* That principle governs every scoping decision below.

> **Status:** Planning only. No code is written yet. This file is the build contract.

---

## 0. Guiding Constraints

- **Time budget: 2–3 hours** for the 7 core requirements; **stretch goals are now mandatory**
  (see below), so plan for an extended build (~4–5h total) and still ship core-first so the
  system is runnable end-to-end before any stretch work lands.
- **Correctness over completeness.** A small system that runs end-to-end beats a broad one that doesn't.
  Even with stretch goals mandatory, core must be green before stretch work starts.
- **Stack:** Python, LangGraph, LangChain, any LLM provider.
- **Definition of done:** all 7 README requirements met **+ all 5 stretch goals implemented**
  + runnable demo + README with the "How I would evaluate this in production" section + public GitHub repo.

### The 7 core requirements (from README/ASSESSMENT — the grading rubric)
1. Hub is a LangGraph `StateGraph` with **typed state** and **explicit edges**.
2. Sub-agents are **separate graphs composed into the hub** — not inlined functions.
3. Tools have **Pydantic input schemas with field descriptions** on every field.
4. Routing uses **LLM structured output** with **confidence score or explicit fallback** (no regex/keywords).
5. **Test ≥2 critical paths**, with documented reasoning for the choice.
6. **Runnable demo or transcript** (simple web view acceptable).
7. **Public GitHub repo** + README incl. the production-evaluation section.

### The 5 mandatory stretch goals (promoted from optional → required by user)
8. **Streaming support** — token/step streaming in the demo surface.
9. **Multi-turn conversation memory** — context persists across turns.
10. **Injury avoidance** — exclude exercises by `joints_loaded` on user constraint.
11. **Bilateral exercise pairing** — auto-include the other side via `bilateral_pair_id`.
12. **Observability** — tracing/structured logging of LLM calls and tool invocations.

> README's "stretch" framing is superseded by the user's explicit instruction to treat these as
> mandatory. The README/ASSESSMENT-wins rule still governs the *core* contract (1–7); items 8–12
> are additive and must not break 1–7.

---

## 1. Tech & Project Decisions (lock these first)

| Decision | Choice | Rationale |
|---|---|---|
| LLM provider | **Anthropic Claude** (`langchain-anthropic`), model `claude-haiku-4-5` for routing/speed, `claude-sonnet-4-6` for generation | `ANTHROPIC_API_KEY` already in env per machine notes; haiku keeps routing cheap/fast |
| Structured output | `llm.with_structured_output(PydanticModel)` | Required by spec |
| Orchestration | LangGraph `StateGraph` for hub **and** each sub-agent (3 sub-graphs compiled, then added as nodes) | Satisfies req #1 & #2 explicitly |
| Tool-calling agent | LangGraph prebuilt `create_react_agent` *or* a hand-rolled tool node loop for the Workout Generator | Prebuilt is fastest path; wrap as a compiled graph so it composes into the hub |
| Fuzzy matching | `rapidfuzz` (`token_sort_ratio`) against exercise `name` field | No LLM call needed for matching; deterministic + testable |
| Demo surface | **CLI with streaming** (guaranteed) + minimal Streamlit/FastAPI view (now in-scope to showcase streaming) | CLI is lowest-risk path to req #6; streaming is mandatory (#8) |
| Config | `.env` via `python-dotenv`; `pip`/`requirements.txt` (or `uv`) | Simple, reproducible |
| Tests | `pytest`; mock the LLM where determinism matters | Req #5 |
| **Memory (#9)** | LangGraph **`MemorySaver` checkpointer** + `thread_id`; `messages` in state | Native LangGraph multi-turn; minimal code |
| **Streaming (#8)** | `graph.stream(..., stream_mode="messages")` / `astream` | Built into LangGraph; surfaces in CLI + web |
| **Observability (#12)** | **Structured logging** (`structlog` or stdlib JSON) of every route decision + tool call + latency; optional LangSmith env hook | Cheapest robust path; LangSmith is a free bonus if `LANGSMITH_API_KEY` present |
| **Injury avoidance (#10)** | `search_exercises` gains `exclude_joints` filter on `joints_loaded` | Dataset already has the field |
| **Bilateral pairing (#11)** | `build_workout` auto-adds `bilateral_pair_id` partner when present | Dataset already has the field |

**Env:** read `ANTHROPIC_API_KEY` from environment (already provisioned on this machine — do **not** prompt for it).

---

## 2. Repository Layout

```
1-multi-agent/
├── exercises.json              # provided (50 exercises) — read-only
├── README.md                   # rewrite for submission (setup + prod-eval section)
├── plan.md                     # this file
├── requirements.txt
├── .env.example                # ANTHROPIC_API_KEY=...
├── src/
│   └── fitness_agents/
│       ├── __init__.py
│       ├── state.py            # TypedState definitions (hub + sub-agent states)
│       ├── data.py             # load exercises.json once; index by id/name
│       ├── schemas.py          # all Pydantic models (router decision, tool inputs, log entry)
│       ├── llm.py              # provider factory (get_llm(model=...))
│       ├── router.py           # LLM structured-output router node
│       ├── agents/
│       │   ├── coach.py        # COACH sub-graph
│       │   ├── generator.py    # WORKOUT_GENERATE sub-graph (search + build tools)
│       │   └── logger.py       # WORKOUT_LOG sub-graph (parse + fuzzy match)
│       ├── tools.py            # search_exercises, build_workout (Pydantic-schema tools)
│       ├── observability.py    # structured logging helpers (#12)
│       └── hub.py              # builds + compiles top-level StateGraph (w/ checkpointer #9)
├── app_cli.py                  # runnable demo — streaming + multi-turn (#8, #9)
├── app_web.py                  # minimal Streamlit/FastAPI view — streaming (#8) — now in-scope
└── tests/
    ├── test_routing.py         # critical path 1
    ├── test_resilience.py      # critical path 2
    └── test_stretch.py         # injury-exclude + bilateral-pairing unit tests (#10, #11)
```

---

## 3. Data Layer (`data.py`)

- Load `exercises.json` once at import; expose:
  - `ALL_EXERCISES: list[Exercise]`
  - `by_id: dict[str, Exercise]`
  - `by_name: dict[str, Exercise]`
  - helper `find_fuzzy(query: str, limit=3) -> list[(Exercise, score)]` via rapidfuzz.
- Relevant fields confirmed present: `id, name, muscle_groups, joints_loaded,
  movement_patterns, equipment_required, is_bilateral, side, priority_tier,
  is_reps, is_duration, supports_weight, estimated_rep_duration, bilateral_pair_id`.
- Note: `equipment_required` values are specific (e.g. `"Adjustable Bench - Decline"`,
  `"Barbell"`, `"Plate"`, `"Rack"`) — search must match loosely (case-insensitive substring /
  fuzzy), not exact equality, or every search returns empty.

---

## 4. Schemas (`schemas.py`) — Pydantic, every field documented

- **`RouteName`** — `Literal["COACH", "WORKOUT_GENERATE", "WORKOUT_LOG", "CLARIFY"]`.
- **`RouterDecision`** (structured-output target):
  - `route: RouteName` — chosen route.
  - `confidence: float` — 0.0–1.0 model self-assessed confidence.
  - `reasoning: str` — one-line justification (aids debugging/observability).
- **`SearchExercisesInput`**: `muscle_groups: list[str] | None`, `equipment: list[str] | None`,
  `movement_patterns: list[str] | None`, **`exclude_joints: list[str] | None`** (injury avoidance #10),
  `limit: int = 10` — each with `Field(description=...)`.
- **`BuildWorkoutInput`**: `exercise_ids: list[str]`, `duration_minutes: int`, `focus: str`,
  **`auto_pair_bilateral: bool = True`** (bilateral pairing #11) — `Field(description=...)` on all.
- **`StructuredWorkout`** (build_workout output): `warmup/main/cooldown: list[WorkoutItem]`
  where `WorkoutItem = {exercise_id, name, sets, reps, rest_seconds}`.
- **`LogEntry`** (logger output): `exercise_name_raw`, `matched_exercise_id | None`,
  `matched_exercise_name | None`, `match_confidence: float`, `sets`, `reps`, `weight | None`, `unit`.

---

## 5. Routing (`router.py`) — Requirement #4 + ambiguity handling

- Router node calls `get_llm("haiku").with_structured_output(RouterDecision)` with a system
  prompt describing the 3 routes + examples (reuse the README table).
- **Explicit low-confidence policy (design decision — document in README):**
  - If `confidence < THRESHOLD` (start at **0.6**) → route to **`CLARIFY`**: hub returns a
    clarifying question instead of dispatching. This is the "never silently misroute" guarantee.
  - Ambiguous examples ("Bench press", "I did a workout yesterday, can you adjust it?") should
    land in CLARIFY rather than a guessed sub-agent.
- Router writes `decision` into hub state; the hub's **conditional edge** maps
  `route → node` (`COACH | WORKOUT_GENERATE | WORKOUT_LOG | CLARIFY`).

---

## 6. Hub Graph (`hub.py`) — Requirements #1 & #2

- **Typed state** (`state.py`): `TypedDict` (or Pydantic) with
  `messages`, `user_input`, `decision: RouterDecision | None`, `response: str`.
- Nodes: `router`, `coach`, `generator`, `logger`, `clarify`.
- **`coach`, `generator`, `logger` are each a compiled sub-graph added via `add_node`** —
  this is the literal satisfaction of req #2 ("separate graphs, not inlined functions").
- Edges: `START → router`; **conditional edge** from `router` keyed on `decision.route`;
  each sub-agent node → `END`.
- Compile once; expose `build_hub() -> CompiledGraph`.

---

## 7. Sub-Agents

### 7a. Coach (`agents/coach.py`)
- Minimal `StateGraph`: single LLM node, system prompt = knowledgeable fitness coach.
- Grounding optional; for exercise-specific Qs it may consult `data.py`, but a plain LLM
  answer is acceptable for v1 (correctness-over-completeness).

### 7b. Workout Generator (`agents/generator.py`) — tool-calling
- A compiled graph wrapping a tool-calling agent with **two tools** (`tools.py`):
  - **`search_exercises`** — filters `ALL_EXERCISES` by muscle/equipment/movement (loose match).
    **Injury avoidance (#10):** drops any exercise whose `joints_loaded` intersects `exclude_joints`.
    Returns id+name+key fields. **On empty result → returns a structured "no matches" payload,
    not an exception** (feeds resilience req).
  - **`build_workout`** — validates each `exercise_id` against `by_id`; assembles
    warmup/main/cooldown with sets/reps/rest. **Bilateral pairing (#11):** when
    `auto_pair_bilateral` and an exercise has `bilateral_pair_id`, auto-include the partner
    (dedup, note it was auto-added). **Unknown id → structured error listing the bad ids**,
    not a raise.
- System prompt instructs: search first, then build only from returned ids; if search is empty,
  tell the user what's missing instead of inventing exercises.

### 7c. Workout Logger (`agents/logger.py`)
- Node 1: LLM `with_structured_output(LogEntry-ish)` to parse sets/reps/weight + raw exercise name
  from conversational input.
- Node 2 (deterministic): `find_fuzzy(raw_name)` → fill `matched_exercise_id/name/match_confidence`.
  - Low fuzzy score (< e.g. 70) → mark unmatched + surface top candidates (no hallucinated match).
- Returns structured JSON `LogEntry`.

---

## 8. Resilience (explicit requirement)

| Failure | Handling | Where |
|---|---|---|
| `search_exercises` empty | Return `{"results": [], "message": "no exercises match ..."}`; agent reports gap, does **not** hallucinate | `tools.py` + generator prompt |
| Invalid `build_workout` id / bad schema | Validate against `by_id`; return structured error; agent re-plans or apologizes | `tools.py` |
| LLM emits malformed tool args | LangChain/Pydantic validation error caught; one bounded retry, then graceful message | tool node wrapper |
| Router structured-output failure / parse error | Fall back to `CLARIFY` route | `router.py` |
| Fuzzy match below threshold | Return unmatched + candidates, never force a match | `logger.py` |

---

## 8b. Mandatory Stretch Features (#8–#12) — now part of definition-of-done

| # | Feature | Implementation | Where |
|---|---|---|---|
| 8 | **Streaming** | Hub compiled normally; demo consumes `graph.stream(..., stream_mode="messages")` (CLI) / `astream` (web) and renders tokens incrementally | `app_cli.py`, `app_web.py` |
| 9 | **Multi-turn memory** | Compile hub with `checkpointer=MemorySaver()`; invoke with `config={"configurable": {"thread_id": ...}}`; keep `messages` in state so coach/router see history (enables "adjust my last workout") | `hub.py`, `state.py` |
| 10 | **Injury avoidance** | `exclude_joints` filter in `search_exercises`; generator prompt instructs it to pass user-stated injured joints | `tools.py`, `generator.py`, `schemas.py` |
| 11 | **Bilateral pairing** | `build_workout` auto-includes `bilateral_pair_id` partner (deduped, flagged) | `tools.py` |
| 12 | **Observability** | `observability.py`: a `log_event(kind, **fields)` JSON logger; call it on every route decision (route, confidence), every tool call (name, args, duration, ok/err), and turn latency. If `LANGSMITH_API_KEY` set, enable LangSmith tracing via env (`LANGCHAIN_TRACING_V2`) — zero extra code | `observability.py` + call sites in `router.py`, `tools.py`, `hub.py` |

Acceptance per feature is covered by demo transcript evidence and/or unit tests (§9, §10).

## 9. Testing (`tests/`) — Requirement #5 (pick 2, justify)

**Chosen critical paths + reasoning (document in README):**

1. **`test_routing.py` — routing correctness incl. ambiguity.**
   *Why:* the router is the single point that can silently send a request to the wrong agent;
   it's the highest-leverage correctness surface. Cases: 3 clear routes → correct route;
   ambiguous inputs ("Bench press", "adjust my workout from yesterday") → `CLARIFY` /
   low-confidence (assert no silent misroute). Mock or stub LLM where needed for determinism;
   keep one live-call smoke test optional.

2. **`test_resilience.py` — empty-search + invalid-tool-call recovery.**
   *Why:* the spec explicitly calls out graceful degradation as a grading criterion, and these
   are the failure modes most likely to crash or hallucinate in production. Cases:
   `search_exercises` for absent equipment → empty structured payload, no exception;
   `build_workout` with a bogus exercise id → structured error, no crash.

These two cover the two requirement-named candidate paths.

**Plus `test_stretch.py` (now required, since #10/#11 are mandatory):**
- Injury avoidance: `search_exercises(exclude_joints=["shoulder"])` returns no exercise loading the shoulder.
- Bilateral pairing: `build_workout` on an exercise with a `bilateral_pair_id` includes the partner exactly once.
- (Cheap add) fuzzy-match unit test on the logger.

---

## 10. Demo (`app_cli.py`) — Requirement #6

- REPL loop: read user input → **`hub.stream(...)`** (#8) with a persistent `thread_id` (#9) →
  print route taken + streamed agent response.
- Seed a scripted transcript demonstrating **every** core + stretch behavior:
  coach Q, generate, log, ambiguous→clarify, **a multi-turn "adjust my last workout" exchange (#9)**,
  **an injured-joint request (#10)**, **a bilateral exercise auto-pairing in the output (#11)**, and
  **the structured observability log lines (#12)**. Save to `transcript.md` as committed proof-of-run.
- `app_web.py` (Streamlit, ~40 lines) is **now in-scope** to visibly showcase streaming + multi-turn.

---

## 11. README (submission) — Requirement #6 & #7

Rewrite README to include:
- Setup (install, `.env`, run `python app_cli.py`).
- Architecture diagram/description (hub + 3 sub-graphs + router).
- The explicit **low-confidence routing decision** (threshold → CLARIFY).
- **Required section: "How I would evaluate this system in production"** — cover:
  - *Metrics:* routing accuracy (vs. labeled set), clarification rate, tool-call success rate,
    fuzzy-match precision, latency/cost per turn, end-to-end task completion.
  - *Failure modes to monitor:* silent misroutes, empty-search hallucinations, invalid tool
    calls, fuzzy mismatches, schema-validation failures, LLM timeouts/cost spikes.
  - *Signals it's working:* high routing accuracy + low-but-nonzero clarification rate,
    tool success near 100%, stable latency, no hallucinated exercises in logged sessions.
- Note which parts are stubbed/mocked and why (per the "stub non-core" philosophy).

---

## 12. Build Order (~4–5h; core green first, then mandatory stretch)

**Phase A — core (1–7) must be runnable end-to-end before Phase B:**
1. **(20m)** Scaffolding: layout, `requirements.txt`, `.env.example`, `data.py`, `schemas.py`, `llm.py`,
   `observability.py` skeleton (so log hooks exist from the start — #12).
2. **(20m)** `router.py` + `RouterDecision` + threshold→CLARIFY policy (log the decision — #12).
3. **(15m)** `hub.py` skeleton with conditional edges + stub coach to prove end-to-end routing.
4. **(20m)** `tools.py` (`search_exercises`, `build_workout`) with resilient empty/invalid handling
   **+ `exclude_joints` (#10) and `auto_pair_bilateral` (#11) built in from the start** (cheap once here).
5. **(20m)** `generator.py` tool-calling sub-graph; wire into hub; log tool calls (#12).
6. **(20m)** `logger.py` parse + fuzzy match sub-graph; wire into hub.
7. **(10m)** Flesh out `coach.py`.
8. **(20m)** `app_cli.py` (basic invoke) + `tests/test_routing.py` + `tests/test_resilience.py` green.

**Phase B — mandatory stretch (8, 9) + tests + demo:**
9. **(15m)** Add `MemorySaver` checkpointer + `thread_id` plumbing (#9); verify multi-turn "adjust" flow.
10. **(15m)** Convert demo to streaming (#8) in `app_cli.py`; add `app_web.py` Streamlit view.
11. **(10m)** `tests/test_stretch.py` (injury-exclude #10, bilateral-pair #11) green.
12. **(10m)** Finalize observability (#12): confirm JSON log lines for route + tool + latency;
    wire optional LangSmith env toggle.
13. **(15m)** Capture full `transcript.md` exercising all core + stretch behaviors.
14. **(15m)** README rewrite incl. production-evaluation section + per-feature notes; push to public GitHub repo.

---

## 13. Mandatory Goals 8–12 — status

All five are **required** (promoted from stretch by user). Detailed design lives in **§8b**;
schema/tool hooks in **§4 & §7b**; tests in **§9**; demo evidence in **§10**. Nothing here is optional.
Any genuinely-extra ideas beyond 8–12 (e.g. richer web UI, eval harness) remain true stretch and
only happen after 1–12 are green.

---

## Open Questions (resolve before/while building; sensible defaults chosen)
- **Confidence threshold** for CLARIFY: default **0.6**, tune against ambiguous test cases.
- **Fuzzy match cutoff** in logger: default **70** (rapidfuzz token_sort_ratio).
- **Web view**: treat as optional; CLI transcript is the committed deliverable.
