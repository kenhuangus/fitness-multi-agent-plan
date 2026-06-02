"""Critical path #2 — graceful degradation on empty search and invalid tool calls.

Why this path: the spec calls these out explicitly, and they are the failure modes
most likely to crash the process or make the agent hallucinate exercises in
production. These tests hit the tools directly (no LLM), so they're deterministic.
"""
from fitness_agents import tools


def test_empty_search_returns_message_not_exception():
    # Equipment that is not in the dataset must yield an empty, recoverable result.
    out = tools.search_exercises.invoke({"equipment": ["Kettlebell-zzz-not-real"]})
    assert out["results"] == []
    assert "message" in out and "no" in out["message"].lower()


def test_real_search_still_returns_results():
    out = tools.search_exercises.invoke({"muscle_groups": ["chest"]})
    assert len(out["results"]) > 0


def test_build_workout_invalid_id_is_reported_not_crashed():
    out = tools.build_workout.invoke({"exercise_ids": ["not-a-real-id"]})
    # No valid exercises -> structured error payload, no exception.
    assert "errors" in out
    assert "not-a-real-id" in out["errors"]
    assert "message" in out


def test_build_workout_mixed_valid_and_invalid():
    from fitness_agents import data

    valid_id = data.all_exercises()[0]["id"]
    out = tools.build_workout.invoke({"exercise_ids": [valid_id, "bogus-id"]})
    assert "workout" in out  # the valid one still produced a workout
    assert out["errors"] == ["bogus-id"]
    main_ids = [i["exercise_id"] for i in out["workout"]["main"]]
    assert valid_id in main_ids
