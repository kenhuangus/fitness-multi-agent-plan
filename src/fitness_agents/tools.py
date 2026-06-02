"""Tools for the Workout Generator (req #3: Pydantic input schemas with field
descriptions). Both tools degrade gracefully (req: resilience) — they return
structured payloads on empty results / invalid input instead of raising, so the
agent can recover and never hallucinates exercises.
"""
from __future__ import annotations

from langchain_core.tools import tool

from . import data
from .observability import log_event
from .schemas import BuildWorkoutInput, SearchExercisesInput

# Compact view of an exercise for tool output (keeps token use + hallucination low).
_FIELDS = ("id", "name", "muscle_groups", "equipment_required", "movement_patterns",
           "joints_loaded", "is_bilateral", "bilateral_pair_id")


def _slim(e: dict) -> dict:
    return {k: e.get(k) for k in _FIELDS}


@tool(args_schema=SearchExercisesInput)
def search_exercises(
    muscle_groups=None,
    equipment=None,
    movement_patterns=None,
    exclude_joints=None,
    limit: int = 10,
) -> dict:
    """Search the exercise dataset by muscle groups, equipment, and movement
    patterns, optionally excluding exercises that load injured joints. Returns
    matching exercises. If nothing matches, returns an empty list with a message
    (do NOT invent exercises in that case)."""
    results = data.search(
        muscle_groups=muscle_groups,
        equipment=equipment,
        movement_patterns=movement_patterns,
        exclude_joints=exclude_joints,
        limit=limit,
    )
    log_event(
        "tool_call",
        name="search_exercises",
        muscle_groups=muscle_groups,
        equipment=equipment,
        exclude_joints=exclude_joints,
        n_results=len(results),
    )
    if not results:
        return {
            "results": [],
            "message": (
                "No exercises match those filters. Tell the user no matching "
                "exercises were found (e.g. equipment not in the dataset) and ask "
                "them to adjust the request. Do not invent exercises."
            ),
        }
    return {"results": [_slim(e) for e in results]}


# Heuristic defaults for prescription by priority tier.
def _prescription(ex: dict) -> tuple[int, str, int]:
    tier = ex.get("priority_tier", 2)
    if tier == 1:
        return 4, "5-8", 120
    if tier == 2:
        return 3, "8-12", 90
    return 3, "12-15", 60


@tool(args_schema=BuildWorkoutInput)
def build_workout(
    exercise_ids: list[str],
    duration_minutes: int = 30,
    focus: str = "general",
    auto_pair_bilateral: bool = True,
) -> dict:
    """Assemble a structured workout (warmup / main / cooldown) from the given
    exercise IDs, with sets, reps, and rest. Invalid IDs are reported in an
    'errors' field rather than crashing. When auto_pair_bilateral is true, the
    other side of any bilateral exercise is auto-included."""
    main: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()

    def _item(ex: dict, note: str | None = None) -> dict:
        sets, reps, rest = _prescription(ex)
        return {
            "exercise_id": ex["id"],
            "name": ex["name"],
            "sets": sets,
            "reps": reps,
            "rest_seconds": rest,
            "note": note,
        }

    for ex_id in exercise_ids:
        ex = data.get(ex_id)
        if ex is None:
            # Invalid user-provided ID -> reported, not crashed (resilience).
            errors.append(ex_id)
            continue
        if ex_id in seen:
            continue
        seen.add(ex_id)
        main.append(_item(ex))

        # Bilateral pairing (#11): auto-include the partner side when present.
        if auto_pair_bilateral and ex.get("bilateral_pair_id"):
            pair = data.get(ex["bilateral_pair_id"])
            if pair is not None and pair["id"] not in seen:
                seen.add(pair["id"])
                main.append(_item(pair, note="auto-added bilateral pair"))
            elif pair is None:
                # Partner side not in this dataset subset -> note it, don't error.
                main[-1]["note"] = "bilateral exercise; partner side not in dataset"

    log_event(
        "tool_call",
        name="build_workout",
        n_requested=len(exercise_ids),
        n_main=len(main),
        n_errors=len(errors),
    )

    if not main:
        return {
            "errors": errors,
            "message": (
                "None of the provided exercise IDs were valid. Re-run "
                "search_exercises to obtain valid IDs before building a workout."
            ),
        }

    workout = {
        "focus": focus,
        "duration_minutes": duration_minutes,
        "warmup": [
            {"exercise_id": "_warmup", "name": "Dynamic warmup (mobility + light cardio)",
             "sets": 1, "reps": "5 min", "rest_seconds": 0, "note": None}
        ],
        "main": main,
        "cooldown": [
            {"exercise_id": "_cooldown", "name": "Stretching / cooldown",
             "sets": 1, "reps": "5 min", "rest_seconds": 0, "note": None}
        ],
    }
    result = {"workout": workout}
    if errors:
        result["errors"] = errors
        result["message"] = f"Skipped {len(errors)} invalid exercise ID(s)."
    return result


TOOLS = [search_exercises, build_workout]
