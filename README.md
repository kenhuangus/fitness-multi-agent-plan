# Fitness Coaching Multi-Agent System

A multi-agent fitness assistant built on **LangGraph**. A hub graph routes each user
message — using **LLM structured output** — to one of three independently-composed
sub-agent graphs:

| Route | Example | Sub-agent |
|-------|---------|-----------|
| `COACH` | "What muscles does a deadlift work?" | Answers fitness/exercise questions |
| `WORKOUT_GENERATE` | "Build me a 30 min upper body session with dumbbells" | Tool-calling agent (`search_exercises` + `build_workout`) |
| `WORKOUT_LOG` | "I just did 3x10 bench press at 185 lbs" | Parses + fuzzy-matches → structured JSON log |
| `CLARIFY` | "Bench press" | Asks for clarification when intent is unclear |

The original assessment prompt is in [`ASSESSMENT.md`](./ASSESSMENT.md). A full proof-of-run
is in [`transcript.md`](./transcript.md).

---

## Architecture

```
                     ┌─────────────────────────── Hub StateGraph ───────────────────────────┐
                     │                                                                       │
   user_input ──▶ router (LLM structured output → RouterDecision{route, confidence})         │
                     │        │                                                              │
                     │        ▼  conditional edge on decision.route                          │
                     │   ┌────┴─────────┬──────────────────┬─────────────┐                   │
                     │   ▼              ▼                  ▼             ▼                    │
                     │ COACH      WORKOUT_GENERATE     WORKOUT_LOG     CLARIFY                │
                     │ (graph)    (graph: ReAct +      (graph:         (node)                 │
                     │             search/build tools)  parse→fuzzy)                          │
                     │   └──────────────┴──────────────────┴─────────────┘                   │
                     │                          ▼                                            │
                     │                         END                                           │
                     │   MemorySaver checkpointer (thread_id) → multi-turn memory            │
                     └───────────────────────────────────────────────────────────────────────┘
```

- **Hub** — a `StateGraph` with **typed state** (`HubState`) and **explicit edges**
  ([`hub.py`](src/fitness_agents/hub.py), [`state.py`](src/fitness_agents/state.py)).
- **Sub-agents are separate compiled graphs** added as nodes, not inlined functions
  ([`agents/`](src/fitness_agents/agents/)).
- **Router** uses `llm.with_structured_output(RouterDecision)` — no regex/keywords
  ([`router.py`](src/fitness_agents/router.py)).
- **Tools** have Pydantic input schemas with a description on every field
  ([`schemas.py`](src/fitness_agents/schemas.py), [`tools.py`](src/fitness_agents/tools.py)).

### Project layout

```
src/fitness_agents/
  state.py          # typed hub state
  schemas.py        # Pydantic: RouterDecision, tool inputs, LogEntry, ...
  data.py           # loads exercises.json; loose filtering + rapidfuzz matching
  llm.py            # Anthropic Claude provider factory
  router.py         # structured-output router + low-confidence policy
  tools.py          # search_exercises, build_workout (resilient)
  observability.py  # structured JSON logging of decisions + tool calls
  agents/
    coach.py        # COACH sub-graph
    generator.py    # WORKOUT_GENERATE sub-graph (ReAct tool-calling)
    logger.py       # WORKOUT_LOG sub-graph (parse → fuzzy match)
  hub.py            # composes everything; MemorySaver checkpointer
app_cli.py          # streaming, multi-turn CLI demo
app_web.py          # minimal Streamlit view
tests/              # test_routing.py, test_resilience.py, test_stretch.py
```

---

## Setup

Requires Python 3.10+ and an Anthropic API key.

```bash
pip install -r requirements.txt
cp .env.example .env          # then put your key in .env
#   ANTHROPIC_API_KEY=sk-ant-...
```

Any LangChain-supported provider works; swap the factory in
[`llm.py`](src/fitness_agents/llm.py). Defaults: `claude-haiku-4-5` for routing,
`claude-sonnet-4-6` for the sub-agents.

## Run

```bash
# Scripted demo — hits every route + every mandatory feature, with streaming:
python app_cli.py --demo

# Interactive REPL (persistent thread → multi-turn memory):
python app_cli.py

# Web view (chat UI; every reply has an expandable decision trace — see below):
streamlit run app_web.py

# Tests:
python -m pytest tests/ -q
```

Routing decisions and tool calls are logged as JSON to **stderr**; the conversation
goes to **stdout**. Redirect stderr to a file to keep the chat clean:
`python app_cli.py --demo 2>trace.jsonl`.

### In-UI decision trace (how the routing decision is made)

Every assistant reply in the web view has an expandable **"🔍 Decision trace"** panel that
shows, without leaving the app, exactly how the turn was handled:

1. **`RouterDecision`** (the LLM structured output) — the chosen route, a confidence bar against
   the 0.6 threshold, and the model's reasoning.
2. **LangGraph path** — `START → router → <ROUTE> → … → END` (incl. the `agent`/`tools` hops for
   the tool-calling generator).
3. **Tool calls** — each Pydantic-validated `search_exercises` / `build_workout` / fuzzy-match call.
4. **Pydantic structured outputs** — the logger's `ParsedLog` (parsed sets/reps/weight/unit) and
   the final `LogEntry` JSON.
5. A link to the **full call-tree trace in Langfuse**.

This is powered by an in-process event sink (`observability.capture()`), the same `log_event`
stream that feeds the JSON logs and Langfuse — so the UI panel and the production trace show the
same data.

---

## Demo video & screenshots

- **[`demo/walkthrough.mp4`](demo/walkthrough.mp4)** — a ~7-minute narrated walkthrough (Deepgram
  TTS + ffmpeg) covering the whole system, the architecture with code, how each requirement is
  met, the **in-UI decision trace**, and the Langfuse observability. Rebuild it with
  `python ops/make_slides.py` → screenshot slides →
  `python <skill>/gen_tts_deepgram.py demo/scenes.json demo/audio` → `build_demo.sh`.
- **[`media/screens/`](media/screens/)** — screenshots of every screen: the CLI, each web route
  (coach / generate / log / clarify), the injury + multi-turn-memory exchange, the Langfuse
  trace list + trace detail, and the in-UI decision-trace panels (routing + tool-calling).
- **[`transcript.md`](transcript.md)** — a text proof-of-run of every route + stretch feature.
- **[`skills/narrated-demo/`](skills/narrated-demo/)** — the reusable, self-contained skill that
  produced the walkthrough: a `scenes.json` → styled slides + Deepgram TTS + ffmpeg montage
  pipeline. Drop it into `~/.claude/skills/` or run its scripts directly on any project.

## Observability with local Langfuse (#12)

Tracing is wired through a LangChain `CallbackHandler`. When the `LANGFUSE_*` env vars are set,
every hub turn is traced; when they're absent it's a no-op (the structured JSON logs still emit).

```bash
# 1. Start a local, self-hosted Langfuse (6 services: web/worker/clickhouse/redis/postgres/minio).
#    Host ports are remapped to avoid clashes; the UI lands on http://localhost:3567.
#    ops/.env auto-provisions an org/project/user + API keys on first boot.
cd ops && docker compose -f langfuse-docker-compose.yml up -d && cd ..

# 2. Point the app at it (already in .env.example):
#    LANGFUSE_PUBLIC_KEY=pk-lf-fitness-demo-public
#    LANGFUSE_SECRET_KEY=sk-lf-fitness-demo-secret
#    LANGFUSE_HOST=http://localhost:3567

# 3. Run anything — traces appear under the "Fitness Multi-Agent" project.
python app_cli.py --demo        # login at http://localhost:3567 → demo@fitness.local / fitnessdemo123
```

Each trace is the full LangGraph call tree — the router decision (route + confidence), the
dispatched sub-agent, and every tool call with inputs/outputs — grouped into a session by
`thread_id`. `tracing.py` also picks up LangSmith automatically if `LANGCHAIN_TRACING_V2=true`.

---

## Key design decisions

### Low-confidence routing (no silent misrouting)

The router returns a `RouterDecision{route, confidence, reasoning}`. The explicit policy:

> If the model picks a concrete route but with **confidence < 0.6**, the decision is
> **downgraded to `CLARIFY`** and the hub asks the user to clarify. If the structured
> call itself errors, it also falls back to `CLARIFY`.

This guarantees the system never *silently* misroutes an ambiguous input like
"Bench press" — it asks instead of guessing. The threshold is configurable via
`ROUTER_CONFIDENCE_THRESHOLD`.

### Resilience

- **Empty search** → `search_exercises` returns `{"results": [], "message": ...}` and the
  generator prompt instructs it to report the gap rather than invent exercises.
- **Invalid tool call** → `build_workout` validates each ID against the dataset and returns
  a structured `errors` payload instead of raising; the agent re-searches.
- **Router / parser LLM errors** → caught and degraded (CLARIFY / raw entry), never crash.
- **Uncertain fuzzy match** → below score 70 the logger returns the entry **unmatched** with
  candidate suggestions; it never forces a hallucinated match.

### Loose matching

`exercises.json` uses very specific equipment strings (e.g. `"Adjustable Bench - Decline"`),
so search uses case-insensitive substring matching, and the logger uses `rapidfuzz` `WRatio`
("bench press" → "Barbell Decline Bench Press", score 77).

---

## Feature coverage

**Core requirements** — all met: typed `StateGraph` hub; sub-agents as separate composed
graphs; Pydantic tool schemas with field descriptions; structured-output routing with a
confidence/fallback policy; the two tools; the parse-and-fuzzy logger; empty-search and
invalid-tool-call resilience; tests; runnable demo.

**Stretch goals — all implemented** (treated as required for this build):

| Goal | Where | Evidence |
|------|-------|----------|
| Streaming | `app_cli.py`, `app_web.py` via `stream(..., stream_mode="messages", subgraphs=True)` | live token streaming for coach/generator |
| Multi-turn memory | `MemorySaver` checkpointer + `thread_id` | transcript: "make that session 25 minutes and focus on legs" remembers the shoulder constraint |
| Injury avoidance | `search_exercises(exclude_joints=...)` filters `joints_loaded` | transcript: shoulder-injury request, all exercises shoulder-safe |
| Bilateral pairing | `build_workout(auto_pair_bilateral=True)` follows `bilateral_pair_id` | `test_stretch.py`; gracefully notes when the partner side isn't in the 50-item sample |
| Observability | `observability.py` JSON logs + optional LangSmith env toggle | the `<details>` log blocks in `transcript.md` |

> **Note on bilateral pairing:** none of the 18 paired exercises in the 50-item sample have
> their partner side *also* in the sample, so the auto-include never fires on real data — the
> tool notes "partner side not in dataset" instead of erroring. The code path is verified in
> `test_stretch.py` by wiring two real exercises into a pair.

---

## Testing — which paths and why

We test three things; the first two are the spec's named "critical paths."

1. **Routing correctness, especially the low-confidence guard** (`test_routing.py`).
   The router is the single point that can silently send a request to the wrong agent —
   the highest-leverage correctness surface. We mock the LLM to test the *policy*
   deterministically: high confidence passes through, low confidence downgrades to
   `CLARIFY`, an explicit `CLARIFY` is respected, and an LLM error falls back to `CLARIFY`.

2. **Graceful degradation** (`test_resilience.py`). Empty search and invalid tool calls are
   the failure modes most likely to crash the process or trigger hallucination in production,
   and the spec calls them out. Deterministic, no LLM.

3. **Mandatory features** (`test_stretch.py`). Injury exclusion, bilateral pairing (both
   directions of the toggle), and fuzzy matching — deterministic guards so these don't
   silently regress.

```
$ python -m pytest tests/ -q
13 passed
```

---

## How I would evaluate this system in production

**What to measure.** The router is the spine of the system, so routing quality is the first
metric I'd track. I'd maintain a labeled set of real user messages (including deliberately
ambiguous ones) and compute **routing accuracy** plus a **confusion matrix** across the four
routes. Because the design's safety valve is "ask instead of guess," I'd watch the
**clarification rate** as a paired metric: a rate that is too high means the threshold is
miscalibrated or prompts are unclear (users get nagged); a rate near zero combined with
falling accuracy means the system is confidently misrouting. The healthy signal is high
accuracy with a small, stable clarification rate on genuinely ambiguous traffic. I'd also
log the **confidence distribution** and periodically re-tune `ROUTER_CONFIDENCE_THRESHOLD`
against it (e.g. precision/recall of the "act vs. clarify" decision).

For the sub-agents I'd track **tool-call success rate** (fraction of `search_exercises` /
`build_workout` calls that validate and return usable output), **empty-search rate** (a proxy
for dataset coverage gaps and a leading indicator of user frustration), and **fuzzy-match
quality** — the distribution of match scores and the rate of "no confident match" outcomes in
the logger, sampled against human labels to estimate precision. End-to-end I'd watch
**task-completion rate** (did the user get a workout / a logged entry / an answer without
bailing), **latency per turn** (p50/p95, split by route since the tool-calling generator is
the slow path), and **token cost per turn**.

**Failure modes to monitor.** The dangerous ones are *silent*: a confident misroute, or a
hallucinated exercise when search came back empty. Both are designed against here (low-
confidence → CLARIFY; empty-search → explicit "no matches, don't invent"), but I'd add an
output guard that cross-checks any exercise the generator names against the dataset and
alarms on out-of-vocabulary names — that catches regressions in the prompt or model. I'd also
monitor schema-validation failures on tool calls and structured output (a spike usually means
a model/version change broke the contract), provider timeouts and error rates, and fuzzy
mismatches where a wrong exercise was logged with high confidence (the most damaging logger
error, since it corrupts the user's training history).

**How I'd know it's working.** Routing accuracy stays high while the clarification rate stays
low-but-nonzero on ambiguous traffic; tool-call success sits near 100% with a bounded empty-
search rate; zero hallucinated-exercise alarms; logged entries match user intent on spot-
checks; and p95 latency and cost-per-turn stay flat release-over-release. Operationally, the
structured JSON logs already emitted here (route decisions with confidence, every tool call
with duration and result counts) are exactly the event stream you'd ship to a dashboard or
LangSmith; setting `LANGCHAIN_TRACING_V2=true` turns on full call-level tracing with no code
change. The cheapest high-value addition in production would be a thumbs-up/down on each turn,
joined to the route and confidence, to build the labeled set that drives everything above.

**What's stubbed (by design).** Per the brief's "stub anything non-core" guidance: there is no
persistence (logs are returned as JSON, not written to a DB), no auth/accounts, and
`build_workout` uses simple priority-tier heuristics for sets/reps/rest rather than a
periodization model. These are deliberate — the architecture (routing, composed graphs,
resilient tools) is the part that matters, and each stub is a clean seam to extend.
