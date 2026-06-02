"""Render each scene in demo/scenes.json to a 1920x1080 HTML slide.
Screen scenes embed the screenshot (base64) fit-to-area with a caption.
"""
import base64
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scenes = json.load(open(os.path.join(ROOT, "demo", "scenes.json"), encoding="utf-8"))

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;
  font-family:'Segoe UI',system-ui,Arial,sans-serif;background:#0d1117;color:#e6edf3}
.slide{width:1920px;height:1080px;display:flex;flex-direction:column;
  padding:70px 90px;position:relative}
.kicker{color:#d2a8ff;font-size:26px;font-weight:700;letter-spacing:3px;text-transform:uppercase}
h1{font-size:88px;font-weight:800;line-height:1.05;margin-top:18px;
  background:linear-gradient(90deg,#79c0ff,#d2a8ff);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent}
.sub{font-size:40px;color:#8b949e;margin-top:30px;font-weight:500}
.bar{font-size:40px;font-weight:700;color:#e6edf3;margin-bottom:26px}
.cap{font-size:30px;color:#8b949e;margin-top:22px}
.imgwrap{flex:1;display:flex;align-items:center;justify-content:center;
  background:#161b22;border:1px solid #30363d;border-radius:16px;padding:22px;min-height:0}
.imgwrap img{max-width:100%;max-height:100%;object-fit:contain;border-radius:8px;
  box-shadow:0 8px 30px rgba(0,0,0,.5)}
ul{margin-top:40px;list-style:none}
li{font-size:40px;line-height:1.45;margin:24px 0;padding-left:54px;position:relative;color:#e6edf3}
li:before{content:'';position:absolute;left:0;top:16px;width:22px;height:22px;border-radius:6px;
  background:linear-gradient(135deg,#79c0ff,#d2a8ff)}
.footer{position:absolute;bottom:42px;left:90px;color:#586069;font-size:24px}
.center{justify-content:center}
/* architecture diagram */
.diagram{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:30px}
.node{background:#161b22;border:2px solid #30363d;border-radius:14px;padding:24px 40px;
  font-size:34px;font-weight:700;text-align:center}
.router{border-color:#d2a8ff;color:#d2a8ff}
.row{display:flex;gap:34px}
.leaf{background:#161b22;border:2px solid #444c56;border-radius:14px;padding:22px 30px;
  font-size:28px;font-weight:700;text-align:center;min-width:300px}
.leaf small{display:block;color:#8b949e;font-weight:500;font-size:22px;margin-top:8px}
.arrow{color:#586069;font-size:40px}
.memo{color:#7ee787;font-size:30px;margin-top:10px}
.foot-brand{position:absolute;bottom:42px;right:90px;color:#586069;font-size:24px}
/* code slide */
.subline{font-size:32px;color:#8b949e;margin:6px 0 24px}
.codewrap{flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0}
pre.code{background:#0b0f14;border:1px solid #30363d;border-radius:14px;
  padding:30px 38px;font-family:'Cascadia Code','Consolas',monospace;font-size:27px;
  line-height:1.45;color:#e6edf3;white-space:pre;overflow:hidden;margin:0}
.cmt{color:#7ee787}
.kw{color:#ff7b72}
/* requirement map */
table.reqmap{width:100%;border-collapse:collapse;margin-top:24px;font-size:28px}
.reqmap td{border-bottom:1px solid #21262d;padding:15px 12px;vertical-align:top}
.reqmap .r{color:#79c0ff;font-weight:700;width:40%}
.reqmap .h{color:#c9d1d9}
.reqmap code{color:#d2a8ff;font-family:'Cascadia Code','Consolas',monospace;font-size:25px}
"""

FOOTER = "Fitness Coaching Multi-Agent · LangGraph · Python · Claude"


def data_uri(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def render(scene):
    k = scene["kind"]
    if k == "title":
        body = f"""<div class="slide center">
          <div class="kicker">Take-home · AI Engineering</div>
          <h1>{html.escape(scene['title'])}</h1>
          <div class="sub">{html.escape(scene['subtitle'])}</div>
          <div class="foot-brand">{FOOTER}</div></div>"""
    elif k == "architecture":
        body = f"""<div class="slide">
          <div class="kicker">How it works</div>
          <div class="bar" style="font-size:64px">{html.escape(scene['title'])}</div>
          <div class="diagram">
            <div class="node">User message</div>
            <div class="arrow">▼</div>
            <div class="node router">Router · LLM structured output<br><small style="font-size:24px;color:#8b949e;font-weight:500">RouterDecision {{ route, confidence }}</small></div>
            <div class="arrow">▼ &nbsp; conditional edge on route</div>
            <div class="row">
              <div class="leaf">COACH<small>fitness Q&amp;A</small></div>
              <div class="leaf">WORKOUT_GENERATE<small>tool-calling: search + build</small></div>
              <div class="leaf">WORKOUT_LOG<small>parse + fuzzy match</small></div>
              <div class="leaf">CLARIFY<small>low-confidence guard</small></div>
            </div>
            <div class="memo">Each sub-agent = a separate compiled StateGraph · MemorySaver checkpointer → multi-turn memory</div>
          </div>
          <div class="foot-brand">{FOOTER}</div></div>"""
    elif k == "screen":
        body = f"""<div class="slide">
          <div class="bar">{html.escape(scene['title'])}</div>
          <div class="imgwrap"><img src="{data_uri(scene['image'])}"></div>
          <div class="cap">{html.escape(scene.get('caption',''))}</div></div>"""
    elif k == "code":
        lines = []
        for ln in scene["code"].split("\n"):
            esc = html.escape(ln)
            if ln.lstrip().startswith("#"):
                lines.append(f'<span class="cmt">{esc}</span>')
            else:
                lines.append(esc)
        code_html = "\n".join(lines)
        body = f"""<div class="slide">
          <div class="kicker">Architecture · {html.escape(scene.get('req',''))}</div>
          <div class="bar" style="font-size:54px;margin-top:10px">{html.escape(scene['title'])}</div>
          <div class="subline">{html.escape(scene.get('subtitle',''))}</div>
          <div class="codewrap"><pre class="code">{code_html}</pre></div>
          <div class="foot-brand">{FOOTER}</div></div>"""
    elif k == "reqmap":
        rows = "".join(
            f'<tr><td class="r">{html.escape(r[0])}</td><td class="h">{r[1]}</td></tr>'
            for r in scene["rows"]
        )
        body = f"""<div class="slide">
          <div class="kicker">Submission</div>
          <div class="bar" style="font-size:56px;margin-top:10px">{html.escape(scene['title'])}</div>
          <table class="reqmap">{rows}</table>
          <div class="foot-brand">{FOOTER}</div></div>"""
    elif k == "bullets":
        lis = "".join(f"<li>{html.escape(b)}</li>" for b in scene["bullets"])
        body = f"""<div class="slide">
          <div class="kicker">Submission</div>
          <div class="bar" style="font-size:64px;margin-top:14px">{html.escape(scene['title'])}</div>
          <ul>{lis}</ul>
          <div class="foot-brand">{FOOTER}</div></div>"""
    else:
        body = f"<div class='slide'><h1>{html.escape(scene['title'])}</h1></div>"

    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


out_dir = os.path.join(ROOT, "demo", "slides")
for s in scenes:
    fn = f"{s['id']}-{s['name']}.html"
    with open(os.path.join(out_dir, fn), "w", encoding="utf-8") as f:
        f.write(render(s))
    print("wrote", fn)
print("done")
