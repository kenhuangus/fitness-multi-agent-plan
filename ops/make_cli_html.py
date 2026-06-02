"""Render a focused CLI session as a terminal-styled HTML page for screenshotting."""
import html

# A curated, compact CLI session (real output, trimmed for a single screen).
SESSION = [
    ("$ python app_cli.py --demo", "cmd"),
    ("=== Fitness Multi-Agent — scripted demo (Langfuse tracing ON) ===", "dim"),
    ("", "plain"),
    ("user: What muscles does a deadlift work?", "user"),
    ("[routed -> COACH]", "route"),
    ("assistant: The deadlift is a full-body pull — primary movers are the", "asst"),
    ("  hamstrings, glutes, erector spinae and quads; lats, traps and core", "asst"),
    ("  stabilize. One of the most efficient compound lifts you can do.", "asst"),
    ("", "plain"),
    ("user: Build me a 20 min upper body workout with dumbbells", "user"),
    ("[routed -> WORKOUT_GENERATE]", "route"),
    ("assistant: [search_exercises ...] [build_workout ...]", "tool"),
    ("  20-minute Upper Body Dumbbell Workout — warmup / main / cooldown", "asst"),
    ("  1. Dumbbell Neutral-Grip Bench Press   3 x 8-12   90s", "asst"),
    ("  2. Alternating Dumbbell Overhead Press  3 x 8-12   90s", "asst"),
    ("", "plain"),
    ("user: I just did 3x10 bench press at 185 lbs", "user"),
    ("[routed -> WORKOUT_LOG]", "route"),
    ('assistant: Logged: 3x10 Barbell Decline Bench Press @ 185 lbs', "asst"),
    ('  (fuzzy-matched "bench press", confidence 0.77) -> structured JSON', "asst"),
    ("", "plain"),
    ("user: Bench press", "user"),
    ("[routed -> CLARIFY]", "route"),
    ("assistant: I'm not sure what you'd like — a fitness question, a workout,", "asst"),
    ("  or logging one? A little more detail will help me route correctly.", "asst"),
]

COLORS = {
    "cmd": "#7ee787", "dim": "#8b949e", "user": "#79c0ff", "route": "#d2a8ff",
    "asst": "#e6edf3", "tool": "#ffa657", "plain": "#e6edf3",
}

rows = []
for text, kind in SESSION:
    c = COLORS.get(kind, "#e6edf3")
    weight = "600" if kind in ("user", "route", "cmd") else "400"
    rows.append(f'<div style="color:{c};font-weight:{weight}">{html.escape(text) or "&nbsp;"}</div>')

page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#0d1117;font-family:'Cascadia Code','Consolas',monospace}}
.term{{max-width:1100px;margin:28px auto;border-radius:10px;overflow:hidden;
  box-shadow:0 10px 40px rgba(0,0,0,.5);border:1px solid #30363d}}
.bar{{background:#161b22;padding:10px 14px;display:flex;align-items:center;gap:8px}}
.dot{{width:12px;height:12px;border-radius:50%}}
.body{{padding:18px 22px;font-size:15px;line-height:1.55}}
.title{{color:#8b949e;margin-left:10px;font-size:13px}}
</style></head><body>
<div class="term">
  <div class="bar">
    <span class="dot" style="background:#ff5f56"></span>
    <span class="dot" style="background:#ffbd2e"></span>
    <span class="dot" style="background:#27c93f"></span>
    <span class="title">app_cli.py — Fitness Multi-Agent (streaming + memory + Langfuse)</span>
  </div>
  <div class="body">{''.join(rows)}</div>
</div></body></html>"""

with open("media/cli_terminal.html", "w", encoding="utf-8") as f:
    f.write(page)
print("wrote media/cli_terminal.html")
