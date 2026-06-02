"""Small shared helpers."""
from __future__ import annotations

from typing import Any


def extract_text(content: Any) -> str:
    """Flatten LangChain/Anthropic message content to plain text.

    Anthropic returns message content as either a string or a list of content
    blocks (dicts like {"type": "text", "text": "..."} or objects with a .text
    attribute). This normalizes both to a single string.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type", "text") == "text" and block.get("text"):
                    parts.append(block["text"])
            else:  # object with a .text attribute
                txt = getattr(block, "text", None)
                if txt:
                    parts.append(txt)
        return "".join(parts)
    return str(content)
