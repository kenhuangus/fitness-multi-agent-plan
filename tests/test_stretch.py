"""Mandatory-feature tests: injury avoidance (#10), bilateral pairing (#11),
fuzzy matching (logger). All deterministic — no LLM calls.
"""
from fitness_agents import data, tools


def test_injury_avoidance_excludes_joint():
    # No returned exercise may load an excluded joint.
    results = data.search(exclude_joints=["shoulder"], limit=50)
    assert results, "expected some non-shoulder exercises to exist"
    for ex in results:
        assert "shoulder" not in [j.lower() for j in ex["joints_loaded"]]


def test_search_tool_passes_exclude_joints():
    out = tools.search_exercises.invoke(
        {"muscle_groups": ["chest"], "exclude_joints": ["shoulder"]}
    )
    for ex in out["results"]:
        assert "shoulder" not in [j.lower() for j in ex["joints_loaded"]]


def test_bilateral_pairing_auto_includes_partner(monkeypatch):
    # The 50-item sample doesn't contain both sides of any pair, so we wire two
    # real exercises into a pair to exercise the auto-include code path.
    ex_a, ex_b = data.all_exercises()[0], data.all_exercises()[1]
    table = dict(data.by_id())
    a = dict(ex_a)
    a["bilateral_pair_id"] = ex_b["id"]
    table[a["id"]] = a
    monkeypatch.setattr(data, "get", lambda eid: table.get(eid))

    out = tools.build_workout.invoke(
        {"exercise_ids": [a["id"]], "auto_pair_bilateral": True}
    )
    main_ids = [i["exercise_id"] for i in out["workout"]["main"]]
    assert ex_b["id"] in main_ids, "bilateral partner should be auto-included"
    paired = [i for i in out["workout"]["main"] if i["exercise_id"] == ex_b["id"]][0]
    assert "bilateral" in (paired["note"] or "")


def test_bilateral_pairing_can_be_disabled(monkeypatch):
    ex_a, ex_b = data.all_exercises()[0], data.all_exercises()[1]
    table = dict(data.by_id())
    a = dict(ex_a)
    a["bilateral_pair_id"] = ex_b["id"]
    table[a["id"]] = a
    monkeypatch.setattr(data, "get", lambda eid: table.get(eid))

    out = tools.build_workout.invoke(
        {"exercise_ids": [a["id"]], "auto_pair_bilateral": False}
    )
    main_ids = [i["exercise_id"] for i in out["workout"]["main"]]
    assert ex_b["id"] not in main_ids


def test_fuzzy_match_resolves_colloquial_name():
    matches = data.find_fuzzy("bench press")
    assert matches, "expected at least one fuzzy match"
    top_name, top_score = matches[0][0]["name"], matches[0][1]
    assert "Bench Press" in top_name
    assert top_score >= 70  # above the logger's match threshold
