"""Langfuse tracing integration (#12).

If LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST are set, every hub
invocation is traced to Langfuse via a LangChain CallbackHandler. When the keys
are absent, this is a no-op — the app still runs and still emits the structured
JSON logs from observability.py.

Use `run_config(thread_id)` to build the config passed to hub.invoke/stream so the
Langfuse callback (when enabled) and the thread_id are attached consistently.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)


def langfuse_enabled() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
        and os.environ.get("LANGFUSE_HOST")
    )


@lru_cache(maxsize=1)
def _handler():
    """Return a cached Langfuse CallbackHandler, or None if not configured/importable."""
    if not langfuse_enabled():
        return None
    try:
        # Initialize the Langfuse client singleton from env, then build the handler.
        from langfuse import Langfuse  # noqa: F401
        from langfuse.langchain import CallbackHandler

        Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ["LANGFUSE_HOST"],
        )
        return CallbackHandler()
    except Exception as exc:  # noqa: BLE001 - tracing must never break the app
        print(f"[tracing] Langfuse disabled: {exc!r}")
        return None


def run_config(thread_id: str, **metadata: Any) -> dict:
    """Build the LangGraph run config: thread_id for memory + Langfuse callback +
    trace metadata (so traces are searchable by thread/session)."""
    cfg: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    handler = _handler()
    if handler is not None:
        cfg["callbacks"] = [handler]
        cfg["metadata"] = {
            "langfuse_session_id": thread_id,
            "langfuse_tags": ["fitness-multi-agent"],
            **metadata,
        }
    return cfg


def flush() -> None:
    """Flush buffered traces to Langfuse (call before a short-lived process exits)."""
    handler = _handler()
    if handler is None:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:  # noqa: BLE001
        pass
