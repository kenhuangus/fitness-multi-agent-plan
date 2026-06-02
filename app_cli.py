"""Runnable CLI demo with streaming (#8) and multi-turn memory (#9).

Usage:
    python app_cli.py            # interactive REPL (one persistent thread)
    python app_cli.py --demo     # scripted run hitting every route + stretch feature

Routing decisions and tool calls are logged as JSON to stderr (observability #12),
so keep stdout (the conversation) and stderr (the trace) separate when reading.
"""
from __future__ import annotations

import sys

# Windows consoles default to cp1252 and choke on emoji/unicode in responses.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, "src")

from langchain_core.messages import AIMessageChunk  # noqa: E402

from fitness_agents.hub import build_hub  # noqa: E402
from fitness_agents.tracing import flush, langfuse_enabled, run_config  # noqa: E402
from fitness_agents.utils import extract_text  # noqa: E402

THREAD_ID = "cli-session"
THREAD = {"configurable": {"thread_id": THREAD_ID}}  # for hub.get_state()


def stream_turn(hub, user_input: str) -> None:
    """Invoke the hub and stream the sub-agent's response tokens as they arrive (#8).

    subgraphs=True surfaces token chunks from inside the sub-agent graphs. The
    router's own structured-output chunks (node 'router', list content) are
    skipped. Nodes that build their reply as a plain state update (logger,
    clarify) don't emit token chunks, so we print their final response from state.
    """
    print(f"\n\033[1muser:\033[0m {user_input}")
    header_printed = False
    streamed_chars = 0

    for _ns, (chunk, meta) in hub.stream(
        {"user_input": user_input, "messages": []},
        run_config(THREAD_ID),
        stream_mode="messages",
        subgraphs=True,
    ):
        node = meta.get("langgraph_node", "")
        if node == "router":
            continue
        if not header_printed:
            route = hub.get_state(THREAD).values.get("decision")
            label = route.route if route else node
            print(f"\033[2m[routed -> {label}]\033[0m")
            print("\033[1massistant:\033[0m ", end="", flush=True)
            header_printed = True
        if isinstance(chunk, AIMessageChunk):
            text = extract_text(chunk.content)
            if text:
                print(text, end="", flush=True)
                streamed_chars += len(text)

    state = hub.get_state(THREAD).values
    if not header_printed:
        label = state["decision"].route if state.get("decision") else "?"
        print(f"\033[2m[routed -> {label}]\033[0m")
        print(f"\033[1massistant:\033[0m {state.get('response','')}")
    elif streamed_chars == 0:
        # Non-streaming responder (logger/clarify) — print final response once.
        print(state.get("response", ""))
    print()


DEMO_SCRIPT = [
    "What muscles does a deadlift work?",                         # COACH
    "Build me a 20 min upper body workout with dumbbells",        # WORKOUT_GENERATE (tools)
    "I just did 3x10 bench press at 185 lbs",                     # WORKOUT_LOG (fuzzy)
    "Bench press",                                                # ambiguous -> CLARIFY
    "My right shoulder is injured, give me a 15 min leg workout", # injury avoidance (#10)
    "Actually make that lower body session 25 minutes instead",  # multi-turn memory (#9)
    "I tried to do 4 sets of zoolander curls",                    # fuzzy miss -> candidates
]


def main() -> None:
    hub = build_hub(with_memory=True)
    trace_note = "Langfuse tracing ON" if langfuse_enabled() else "Langfuse tracing off"
    if "--demo" in sys.argv:
        print(f"=== Fitness Multi-Agent — scripted demo ({trace_note}) ===")
        for line in DEMO_SCRIPT:
            stream_turn(hub, line)
        flush()
        return
    print(f"Fitness Multi-Agent (LangGraph). {trace_note}. Type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("\033[1myou>\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user_input.lower() in {"quit", "exit", "q"}:
            break
        if user_input:
            stream_turn(hub, user_input)
    flush()


if __name__ == "__main__":
    main()
