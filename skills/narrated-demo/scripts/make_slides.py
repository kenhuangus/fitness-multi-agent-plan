#!/usr/bin/env python3
"""Render a scenes.json into 1920x1080 HTML slides (one NN-name.html per scene).

Usage:
    python make_slides.py <scenes.json> <out_dir> [--footer "TEXT"] [--assets DIR]

Each scene is an object with an "id" (zero-padded ordinal), a "name", a "kind",
and kind-specific fields. Supported kinds:

  title      { title, subtitle?, kicker? }
  bullets    { title, bullets:[...], kicker? }
  code       { title, subtitle?, code, kicker? }     # comments (# / //) dimmed green
  table      { title, rows:[[left, right_html], ...], kicker? }
  image      { title, image, caption? }              # embeds a screenshot, fit-to-area
  diagram    { title, nodes:[...], note? }           # vertical flow; see README

Image paths are resolved relative to --assets (default: the scenes.json directory).
Pair the output with scripts/capture_slides.sh to turn each .html into a .png,
then gen_tts_deepgram.py + build_demo.sh to make the narrated MP4.
"""
from __future__ import annotations

import base64
import html
import json
import os
import sys

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
.bar{font-size:54px;font-weight:800;color:#e6edf3;margin-bottom:20px}
.cap{font-size:30px;color:#8b949e;margin-top:22px}
.imgwrap{flex:1;display:flex;align-items:center;justify-content:center;
  background:#161b22;border:1px solid #30363d;border-radius:16px;padding:22px;min-height:0}
.imgwrap img{max-width:100%;max-height:100%;object-fit:contain;border-radius:8px;
  box-shadow:0 8px 30px rgba(0,0,0,.5)}
ul{margin-top:40px;list-style:none}
li{font-size:40px;line-height:1.45;margin:24px 0;padding-left:54px;position:relative;color:#e6edf3}
li:before{content:'';position:absolute;left:0;top:16px;width:22px;height:22px;border-radius:6px;
  background:linear-gradient(135deg,#79c0ff,#d2a8ff)}
.center{justify-content:center}
.diagram{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px}
.node{background:#161b22;border:2px solid #30363d;border-radius:14px;padding:22px 40px;
  font-size:34px;font-weight:700;text-align:center}
.node.accent{border-color:#d2a8ff;color:#d2a8ff}
.node small,.leaf small{display:block;color:#8b949e;font-weight:500;font-size:22px;margin-top:8px}
.row{display:flex;gap:30px;flex-wrap:wrap;justify-content:center}
.leaf{background:#161b22;border:2px solid #444c56;border-radius:14px;padding:20px 28px;
  font-size:28px;font-weight:700;text-align:center;min-width:280px}
.arrow{color:#586069;font-size:38px}
.note{color:#7ee787;font-size:30px;margin-top:8px;text-align:center}
.subline{font-size:32px;color:#8b949e;margin:6px 0 24px}
.codewrap{flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0}
pre.code{background:#0b0f14;border:1px solid #30363d;border-radius:14px;
  padding:30px 38px;font-family:'Cascadia Code','Consolas',monospace;font-size:27px;
  line-height:1.45;color:#e6edf3;white-space:pre;overflow:hidden;margin:0}
.cmt{color:#7ee787}
table.tbl{width:100%;border-collapse:collapse;margin-top:24px;font-size:28px}
.tbl td{border-bottom:1px solid #21262d;padding:15px 12px;vertical-align:top}
.tbl .l{color:#79c0ff;font-weight:700;width:40%}
.tbl .r{color:#c9d1d9}
.tbl code{color:#d2a8ff;font-family:'Cascadia Code','Consolas',monospace;font-size:25px}
.foot{position:absolute;bottom:42px;right:90px;color:#586069;font-size:24px}
"""


def data_uri(path: str) -> str:
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _code_html(code: str) -> str:
    out = []
    for ln in code.split("\n"):
        esc = html.escape(ln)
        s = ln.lstrip()
        if s.startswith("#") or s.startswith("//"):
            out.append(f'<span class="cmt">{esc}</span>')
        else:
            out.append(esc)
    return "\n".join(out)


def _diagram(nodes: list) -> str:
    parts = []
    for i, n in enumerate(nodes):
        if isinstance(n, dict) and "row" in n:
            leaves = "".join(
                f'<div class="leaf">{html.escape(x.get("label",""))}'
                + (f'<small>{html.escape(x["sub"])}</small>' if x.get("sub") else "")
                + "</div>"
                for x in n["row"]
            )
            parts.append(f'<div class="row">{leaves}</div>')
        else:
            label = html.escape(n.get("label", "")) if isinstance(n, dict) else html.escape(str(n))
            sub = n.get("sub") if isinstance(n, dict) else None
            acc = " accent" if isinstance(n, dict) and n.get("accent") else ""
            inner = label + (f'<small>{html.escape(sub)}</small>' if sub else "")
            parts.append(f'<div class="node{acc}">{inner}</div>')
        if i < len(nodes) - 1:
            parts.append('<div class="arrow">▼</div>')
    return "".join(parts)


def render(scene: dict, footer: str, assets_dir: str) -> str:
    k = scene.get("kind", "bullets")
    kicker = html.escape(scene.get("kicker", ""))

    if k == "title":
        kk = kicker or "Demo"
        body = f"""<div class="slide center">
          <div class="kicker">{kk}</div>
          <h1>{html.escape(scene['title'])}</h1>
          {f'<div class="sub">{html.escape(scene["subtitle"])}</div>' if scene.get('subtitle') else ''}
          <div class="foot">{html.escape(footer)}</div></div>"""
    elif k == "bullets":
        lis = "".join(f"<li>{html.escape(b)}</li>" for b in scene.get("bullets", []))
        body = f"""<div class="slide">
          {f'<div class="kicker">{kicker}</div>' if kicker else ''}
          <div class="bar" style="font-size:64px;margin-top:10px">{html.escape(scene['title'])}</div>
          <ul>{lis}</ul>
          <div class="foot">{html.escape(footer)}</div></div>"""
    elif k == "code":
        body = f"""<div class="slide">
          {f'<div class="kicker">{kicker}</div>' if kicker else ''}
          <div class="bar" style="margin-top:10px">{html.escape(scene['title'])}</div>
          {f'<div class="subline">{html.escape(scene["subtitle"])}</div>' if scene.get('subtitle') else ''}
          <div class="codewrap"><pre class="code">{_code_html(scene['code'])}</pre></div>
          <div class="foot">{html.escape(footer)}</div></div>"""
    elif k == "table":
        rows = "".join(
            f'<tr><td class="l">{html.escape(r[0])}</td><td class="r">{r[1]}</td></tr>'
            for r in scene.get("rows", [])
        )
        body = f"""<div class="slide">
          {f'<div class="kicker">{kicker}</div>' if kicker else ''}
          <div class="bar" style="font-size:56px;margin-top:10px">{html.escape(scene['title'])}</div>
          <table class="tbl">{rows}</table>
          <div class="foot">{html.escape(footer)}</div></div>"""
    elif k == "image":
        img_path = scene["image"]
        if not os.path.isabs(img_path):
            img_path = os.path.join(assets_dir, img_path)
        body = f"""<div class="slide">
          <div class="bar">{html.escape(scene['title'])}</div>
          <div class="imgwrap"><img src="{data_uri(img_path)}"></div>
          {f'<div class="cap">{html.escape(scene["caption"])}</div>' if scene.get('caption') else ''}</div>"""
    elif k == "diagram":
        body = f"""<div class="slide">
          {f'<div class="kicker">{kicker}</div>' if kicker else ''}
          <div class="bar" style="font-size:64px">{html.escape(scene['title'])}</div>
          <div class="diagram">{_diagram(scene.get('nodes', []))}
          {f'<div class="note">{html.escape(scene["note"])}</div>' if scene.get('note') else ''}</div>
          <div class="foot">{html.escape(footer)}</div></div>"""
    else:
        body = f"<div class='slide'><h1>{html.escape(scene.get('title',''))}</h1></div>"

    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    scenes_path, out_dir = argv[1], argv[2]
    footer = "Made with narrated-demo"
    if "--footer" in argv:
        footer = argv[argv.index("--footer") + 1]
    assets_dir = os.path.dirname(os.path.abspath(scenes_path))
    if "--assets" in argv:
        assets_dir = argv[argv.index("--assets") + 1]

    with open(scenes_path, encoding="utf-8") as f:
        scenes = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    for s in scenes:
        fn = f"{s['id']}-{s.get('name','slide')}.html"
        with open(os.path.join(out_dir, fn), "w", encoding="utf-8") as f:
            f.write(render(s, footer, assets_dir))
        print("wrote", fn)
    print(f"DONE {len(scenes)} slides -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
