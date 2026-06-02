"""Pydantic schemas (req #3: every tool field has a description).

Also holds the router's structured-output target and the logger's output schema.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RouteName = Literal["COACH", "WORKOUT_GENERATE", "WORKOUT_LOG", "CLARIFY"]


# --- Routing (#4) ------------------------------------------------------------
class RouterDecision(BaseModel):
    """Structured routing decision emitted by the router LLM."""

    route: RouteName = Field(
        description=(
            "Chosen route. COACH = general fitness/exercise questions. "
            "WORKOUT_GENERATE = build/design a workout. "
            "WORKOUT_LOG = record a completed workout. "
            "CLARIFY = intent is ambiguous or underspecified."
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Self-assessed confidence in the chosen route, 0.0 to 1.0.",
    )
    reasoning: str = Field(
        description="One short sentence justifying the routing decision."
    )


# --- Tool input schemas (#3) -------------------------------------------------
class SearchExercisesInput(BaseModel):
    """Inputs for searching the exercise dataset."""

    muscle_groups: Optional[list[str]] = Field(
        default=None,
        description="Target muscle groups, e.g. ['chest', 'triceps']. Loose match.",
    )
    equipment: Optional[list[str]] = Field(
        default=None,
        description="Available equipment, e.g. ['Dumbbell', 'Barbell']. Loose match.",
    )
    movement_patterns: Optional[list[str]] = Field(
        default=None,
        description="Movement patterns, e.g. ['upper push - horizontal'].",
    )
    exclude_joints: Optional[list[str]] = Field(
        default=None,
        description=(
            "Injured joints to avoid, e.g. ['shoulder']. Any exercise loading one of "
            "these joints is excluded (injury avoidance)."
        ),
    )
    limit: int = Field(
        default=10, ge=1, le=50, description="Maximum number of exercises to return."
    )


class BuildWorkoutInput(BaseModel):
    """Inputs for assembling a structured workout from chosen exercises."""

    exercise_ids: list[str] = Field(
        description="Exercise IDs (from search_exercises results) to include in the main block."
    )
    duration_minutes: int = Field(
        default=30, ge=5, le=180, description="Target total session length in minutes."
    )
    focus: str = Field(
        default="general",
        description="Short label for the session focus, e.g. 'upper body strength'.",
    )
    auto_pair_bilateral: bool = Field(
        default=True,
        description=(
            "If true, when a chosen exercise has a bilateral_pair_id, the paired "
            "(other-side) exercise is auto-included so both sides are trained."
        ),
    )


# --- Workout output ----------------------------------------------------------
class WorkoutItem(BaseModel):
    exercise_id: str
    name: str
    sets: int
    reps: str = Field(description="Reps or duration prescription, e.g. '8-12' or '30s'.")
    rest_seconds: int
    note: Optional[str] = Field(
        default=None, description="Optional note, e.g. 'auto-added bilateral pair'."
    )


class StructuredWorkout(BaseModel):
    focus: str
    duration_minutes: int
    warmup: list[WorkoutItem]
    main: list[WorkoutItem]
    cooldown: list[WorkoutItem]


# --- Logger output -----------------------------------------------------------
class ParsedLog(BaseModel):
    """Raw fields parsed from conversational workout-log input (pre fuzzy-match)."""

    exercise_name_raw: str = Field(
        description="Exercise name exactly as the user phrased it, e.g. 'bench press'."
    )
    sets: Optional[int] = Field(default=None, description="Number of sets performed.")
    reps: Optional[int] = Field(default=None, description="Reps per set.")
    weight: Optional[float] = Field(default=None, description="Weight used, numeric.")
    unit: Optional[str] = Field(
        default=None, description="Weight unit, e.g. 'lbs' or 'kg'."
    )


class LogEntry(BaseModel):
    """Final structured log entry returned to the user (post fuzzy-match)."""

    exercise_name_raw: str
    matched_exercise_id: Optional[str] = None
    matched_exercise_name: Optional[str] = None
    match_confidence: float = 0.0
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight: Optional[float] = None
    unit: Optional[str] = None
    candidates: list[str] = Field(
        default_factory=list,
        description="Top alternative exercise names when the match is uncertain.",
    )
