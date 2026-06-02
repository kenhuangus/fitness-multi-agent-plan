"""Fitness coaching multi-agent system (LangGraph hub + 3 sub-agents)."""

__all__ = ["build_hub"]


def build_hub(*args, **kwargs):
    # Lazy import so `import fitness_agents` doesn't pull LLM deps unless needed.
    from .hub import build_hub as _build_hub

    return _build_hub(*args, **kwargs)
