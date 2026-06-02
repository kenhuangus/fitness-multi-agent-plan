"""LLM provider factory. Anthropic Claude via langchain-anthropic.

Reads ANTHROPIC_API_KEY from the environment (loaded from .env if present).
Routing uses a fast/cheap model; generation uses a stronger one.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

# override=True so .env wins over an ambient empty/placeholder key in the shell.
load_dotenv(override=True)

ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "claude-haiku-4-5")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-4-6")


@lru_cache(maxsize=8)
def get_llm(model: str | None = None, temperature: float = 0.0) -> ChatAnthropic:
    """Return a cached ChatAnthropic client. `model` defaults to AGENT_MODEL."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return ChatAnthropic(
        model=model or AGENT_MODEL,
        temperature=temperature,
        max_tokens=1500,
    )


def get_router_llm() -> ChatAnthropic:
    return get_llm(ROUTER_MODEL)


def get_agent_llm() -> ChatAnthropic:
    return get_llm(AGENT_MODEL)
