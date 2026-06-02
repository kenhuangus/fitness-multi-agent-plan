"""Observability (#12): structured JSON logging of route decisions, tool calls,
and turn latency. If LANGCHAIN_TRACING_V2 is set, LangSmith tracing is picked up
automatically by langchain — no code changes required here.

Every event is a single JSON line on stderr, so it is greppable and ships cleanly
to any log aggregator.
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from typing import Any


def log_event(kind: str, **fields: Any) -> None:
    """Emit one structured JSON log line. `kind` is the event type, e.g.
    'route_decision', 'tool_call', 'turn'."""
    record = {"event": kind, **fields}
    try:
        line = json.dumps(record, default=str)
    except (TypeError, ValueError):
        line = json.dumps({"event": kind, "repr": str(fields)})
    print(line, file=sys.stderr, flush=True)


@contextmanager
def timed(kind: str, **fields: Any):
    """Context manager that logs `kind` with a duration_ms field and ok/error.

    Usage:
        with timed("tool_call", name="search_exercises", args=...):
            ...
    """
    start = time.perf_counter()
    ok = True
    err = None
    try:
        yield
    except Exception as exc:  # noqa: BLE001 - we re-raise after logging
        ok = False
        err = repr(exc)
        raise
    finally:
        dur_ms = round((time.perf_counter() - start) * 1000, 1)
        log_event(kind, duration_ms=dur_ms, ok=ok, error=err, **fields)
