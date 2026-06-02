"""Data layer: load exercises.json once and expose lookups + fuzzy matching.

The dataset (50 exercises) is read-only. `equipment_required` values are very
specific strings (e.g. "Adjustable Bench - Decline", "Barbell"), so all matching
is loose (case-insensitive substring) rather than exact equality, otherwise every
search would return empty.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

# exercises.json lives at the project root (two levels up from this file's package).
_DATA_PATH = Path(__file__).resolve().parents[2] / "exercises.json"

Exercise = dict[str, Any]


@lru_cache(maxsize=1)
def _load() -> list[Exercise]:
    with open(_DATA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def all_exercises() -> list[Exercise]:
    return _load()


@lru_cache(maxsize=1)
def by_id() -> dict[str, Exercise]:
    return {e["id"]: e for e in _load()}


@lru_cache(maxsize=1)
def by_name() -> dict[str, Exercise]:
    return {e["name"]: e for e in _load()}


def get(exercise_id: str) -> Exercise | None:
    return by_id().get(exercise_id)


def _norm(s: str) -> str:
    return s.strip().lower()


def _matches_any(needles: list[str] | None, haystack: list[str]) -> bool:
    """True if no needles given, or any needle is a (case-insensitive) substring
    of any haystack item. Substring (not exact) so 'dumbbell' matches
    'Adjustable Dumbbell'; one-directional so a made-up longer string like
    'Kettlebell-zzz' does NOT match a real shorter item."""
    if not needles:
        return True
    hay = [_norm(h) for h in haystack]
    for n in needles:
        nn = _norm(n)
        if any(nn in h for h in hay):
            return True
    return False


def search(
    muscle_groups: list[str] | None = None,
    equipment: list[str] | None = None,
    movement_patterns: list[str] | None = None,
    exclude_joints: list[str] | None = None,
    limit: int = 10,
) -> list[Exercise]:
    """Filter exercises by loose matching. `exclude_joints` (injury avoidance, #10)
    drops any exercise whose joints_loaded intersects the excluded joints."""
    excl = {_norm(j) for j in (exclude_joints or [])}
    results: list[Exercise] = []
    for e in _load():
        if not _matches_any(muscle_groups, e.get("muscle_groups", [])):
            continue
        if not _matches_any(equipment, e.get("equipment_required", [])):
            continue
        if not _matches_any(movement_patterns, e.get("movement_patterns", [])):
            continue
        if excl and {_norm(j) for j in e.get("joints_loaded", [])} & excl:
            continue
        results.append(e)
        if len(results) >= limit:
            break
    return results


def find_fuzzy(query: str, limit: int = 3) -> list[tuple[Exercise, float]]:
    """Fuzzy-match a free-text exercise name against the dataset.
    Returns (exercise, score 0-100) sorted best-first."""
    names = [e["name"] for e in _load()]
    # WRatio balances partial / token matching: "bench press" -> "Barbell ...
    # Bench Press" scores well while staying discriminating for short queries.
    matches = process.extract(query, names, scorer=fuzz.WRatio, limit=limit)
    out: list[tuple[Exercise, float]] = []
    for name, score, _idx in matches:
        out.append((by_name()[name], float(score)))
    return out
