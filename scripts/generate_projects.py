#!/usr/bin/env python3
"""
generate_projects.py - render the animated, theme-matched projects panel.

    python3 scripts/generate_projects.py data/merged.json assets

Reads data/merged.json (written by fetch_data.py: projects.json + live
GitHub data) and renders a 2-column grid of mini terminal cards, one per
project. Add/remove/reorder projects by editing data/projects.json and
re-running fetch_data.py -- this script and the README never change.

Palette matches hero.py / cards.py / radar.py: near-black, off-white,
emerald, champagne gold. Projects the API can't see (private / not yet
pushed) get a lock badge and no invented stats.
"""
from __future__ import annotations

import base64
import html
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

THEMES = {
    "dark": {
        "BG": "#08090A", "PANEL": "#0F1012", "PANEL_BAR": "#0C0D0E",
        "GOLD": "#D4AF37", "EMERALD": "#10B981", "EMERALD2": "#0D9668",
        "TEXT": "#F5F5F4", "MUTED": "#9CA3AF", "DIM": "#52525B",
        "STROKE": "rgba(212,175,55,0.20)", "STROKE_HI": "rgba(16,185,129,0.55)",
        "STROKE_LO": "rgba(212,175,55,0.16)", "BARLINE": "rgba(255,255,255,0.08)",
        "RING_BG": "rgba(255,255,255,0.10)", "PILL_BG": "rgba(212,175,55,0.10)",
        "PILL_STROKE": "rgba(212,175,55,0.4)", "MONO_TX": "#0A0A0B",
    },
    "light": {
        "BG": "#FAFAF9", "PANEL": "#FFFFFF", "PANEL_BAR": "#F4F4F3",
        "GOLD": "#A67C00", "EMERALD": "#059669", "EMERALD2": "#047857",
        "TEXT": "#101012", "MUTED": "#52525B", "DIM": "#9CA3AF",
        "STROKE": "rgba(166,124,0,0.24)", "STROKE_HI": "rgba(5,150,105,0.55)",
        "STROKE_LO": "rgba(166,124,0,0.18)", "BARLINE": "rgba(0,0,0,0.08)",
        "RING_BG": "rgba(0,0,0,0.10)", "PILL_BG": "rgba(166,124,0,0.08)",
        "PILL_STROKE": "rgba(166,124,0,0.35)", "MONO_TX": "#FFFFFF",
    },
}

DONUT_COLORS_KEYS = ["EMERALD", "GOLD", "EMERALD2", "MUTED"]

W = 1180
CARD_W = 578
CARD_H = 168
GAP = 14
MARGIN = 5
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

ICON_LOCK = ("M4 4v2H3.25A1.25 1.25 0 002 7.25v6.5A1.25 1.25 0 003.25 15h9.5A1.25 1.25 0 "
             "0014 13.75v-6.5A1.25 1.25 0 0012.75 6H12V4a4 4 0 10-8 0zm6.5 2H5.5V4a2.5 2.5 0 "
             "015 0v2z")


def esc(s):
    return html.escape(str(s), quote=True)


def rel_time(iso):
    if not iso:
        return "n/a"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - d
        if delta.days > 365:
            return f"{delta.days // 365}y ago"
        if delta.days > 30:
            return f"{delta.days // 30}mo ago"
        if delta.days > 0:
            return f"{delta.days}d ago"
        h = delta.seconds // 3600
        return f"{h}h ago" if h else "just now"
    except Exception:
        return "n/a"


def load_logo_b64(name, logos_dir: Path):
    if not logos_dir.exists():
        return None
    for ext in ("png", "svg", "jpg", "jpeg", "webp"):
        p = logos_dir / f"{name.lower()}.{ext}"
        if p.exists():
            mime = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg",
                    "jpeg": "image/jpeg", "webp": "image/webp"}[ext]
            return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return None


def wrap_text(s, max_chars, max_lines=2):
    words = s.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words and " ".join(lines).count(" ") + 1 < len(words):
        lines[-1] = lines[-1][:max_chars - 1].rstrip() + "..."
    return lines


def donut_segments(languages, cx, cy, r, begin, c):
    total = sum(languages.values()) or 1
    entries = sorted(languages.items(), key=lambda kv: -kv[1])[:4]
    other = total - sum(v for _, v in entries)
    if other > 0:
        entries.append(("Other", other))
    circumference = 2 * math.pi * r
    out, legend = [], []
    offset = 0.0
    t = begin
    for i, (lang, v) in enumerate(entries):
        frac = v / total
        seg = frac * circumference
        col = c[DONUT_COLORS_KEYS[i % len(DONUT_COLORS_KEYS)]]
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" stroke-width="9" '
            f'stroke-dasharray="{seg:.2f} {circumference - seg:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.01s" begin="{t:.2f}s" fill="freeze"/>'
            f'<animate attributeName="stroke-dasharray" from="0 {circumference:.2f}" '
            f'to="{seg:.2f} {circumference - seg:.2f}" dur="0.6s" begin="{t:.2f}s" fill="freeze" '
            f'calcMode="spline" keyTimes="0;1" keySplines="0.3 0 0.2 1"/></circle>'
        )
        legend.append((lang, frac, col))
        offset += seg
        t += 0.18
    return "".join(out), legend


def card(p, x, y, idx, c, logos_dir):
    begin = 0.25 + idx * 0.15
    e = []
    a = e.append
    repo = p["repo"]
    href = f"https://github.com/{esc(repo)}"
    a(f'<a href="{href}" target="_blank">')
    a(f'<g opacity="0" transform="translate({x},{y})">')
    a(f'<animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{begin:.2f}s" fill="freeze"/>')

    a(f'<rect width="{CARD_W}" height="{CARD_H}" rx="12" fill="{c["PANEL"]}" stroke="{c["STROKE"]}">'
      f'<animate attributeName="stroke" values="{c["STROKE_LO"]};{c["STROKE_HI"]};{c["STROKE_LO"]}" '
      f'dur="4.5s" begin="{begin + idx * 0.7:.2f}s" repeatCount="indefinite"/></rect>')
    a(f'<rect width="{CARD_W}" height="30" rx="12" fill="{c["PANEL_BAR"]}"/>')
    a(f'<rect y="18" width="{CARD_W}" height="12" fill="{c["PANEL_BAR"]}"/>')
    a(f'<line x1="0" y1="30" x2="{CARD_W}" y2="30" stroke="{c["BARLINE"]}"/>')
    a(f'<text x="16" y="19" font-size="10" fill="{c["MUTED"]}">'
      f'<tspan fill="{c["GOLD"]}">&#8226;</tspan> {esc(repo)}</text>')

    if p.get("unavailable"):
        s = 16 / 16
        a(f'<g transform="translate({CARD_W - 30},{8}) scale({s:.3f})" fill="{c["MUTED"]}">'
          f'<path d="{ICON_LOCK}"/></g>')
    else:
        try:
            days = (datetime.now(timezone.utc) -
                    datetime.fromisoformat(p.get("pushed_at", "").replace("Z", "+00:00"))).days
        except Exception:
            days = 999
        if days <= 14:
            a(f'<circle cx="{CARD_W-16}" cy="15" r="3.5" fill="{c["EMERALD"]}">'
              f'<animate attributeName="opacity" values="1;0.25;1" dur="1.8s" repeatCount="indefinite"/></circle>')
        else:
            a(f'<circle cx="{CARD_W-16}" cy="15" r="3.5" fill="{c["DIM"]}"/>')

    logo = load_logo_b64(p.get("name", ""), logos_dir)
    float_anim = (f'<animateTransform attributeName="transform" type="translate" '
                  f'values="0 0; 0 -2.5; 0 0" dur="5s" begin="{begin + idx * 0.5:.2f}s" '
                  f'repeatCount="indefinite" calcMode="spline" keyTimes="0;0.5;1" '
                  f'keySplines="0.4 0 0.6 1;0.4 0 0.6 1"/>')
    if logo:
        a(f'<g>{float_anim}<image x="16" y="44" width="40" height="40" href="{logo}" '
          f'preserveAspectRatio="xMidYMid meet"/></g>')
    else:
        initial = esc((p.get("name") or "?")[0].upper())
        a(f'<g>{float_anim}<rect x="16" y="44" width="40" height="40" rx="9" '
          f'fill="{c["GOLD"]}" opacity="0.92"/>'
          f'<text x="36" y="71" text-anchor="middle" font-size="20" font-weight="700" '
          f'fill="{c["MONO_TX"]}">{initial}</text></g>')

    name = esc(p.get("name", "unnamed"))
    a(f'<text x="68" y="61" font-size="17" font-weight="700" fill="{c["TEXT"]}">{name}'
      f'<tspan fill="{c["EMERALD"]}">_<animate attributeName="opacity" values="1;0;1" dur="1.2s" '
      f'begin="{begin + 0.4:.2f}s" repeatCount="indefinite"/></tspan></text>')

    for i, line in enumerate(wrap_text(p.get("description", "") or "", 52)):
        a(f'<text x="68" y="{80 + i * 16}" font-size="11" fill="{c["MUTED"]}">{esc(line)}</text>')

    tx = 68
    tags = [p["tagline"]] if p.get("tagline") else []
    if p.get("language"):
        tags.append(p["language"])
    for tag in tags[:3]:
        tw = len(tag) * 6.6 + 14
        a(f'<rect x="{tx}" y="118" width="{tw:.0f}" height="17" rx="8.5" '
          f'fill="{c["PILL_BG"]}" stroke="{c["PILL_STROKE"]}"/>')
        a(f'<text x="{tx + tw/2:.0f}" y="130" text-anchor="middle" font-size="9.5" '
          f'fill="{c["GOLD"]}">{esc(tag)}</text>')
        tx += tw + 7

    if p.get("unavailable"):
        a(f'<text x="68" y="155" font-size="11" fill="{c["DIM"]}">private -- stats hidden until public</text>')
    else:
        stars = p.get("stars", 0)
        a(f'<text x="68" y="155" font-size="11" fill="{c["MUTED"]}">'
          f'<tspan fill="{c["GOLD"]}">&#9733;</tspan> {stars}'
          f'<tspan fill="{c["DIM"]}" dx="14">updated {rel_time(p.get("pushed_at"))}</tspan></text>')

    langs = p.get("languages") or {}
    if langs and not p.get("unavailable"):
        cx, cy, r = CARD_W - 58, CARD_H // 2 + 6, 27
        segs, legend = donut_segments(langs, cx, cy, r, begin + 0.3, c)
        a(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c["RING_BG"]}" stroke-width="9"/>')
        a(segs)
        top = legend[0]
        a(f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="11" font-weight="700" '
          f'fill="{c["TEXT"]}">{top[1]*100:.0f}%</text>')
        dot_x = cx - r - 92
        text_x = dot_x + 9
        ly = cy - 22
        for lang, frac, col in legend[:3]:
            a(f'<circle cx="{dot_x}" cy="{ly}" r="3.5" fill="{col}"/>')
            a(f'<text x="{text_x}" y="{ly+4}" font-size="10" fill="{c["MUTED"]}">'
              f'{esc(lang)} {frac*100:.0f}%</text>')
            ly += 18
    elif p.get("unavailable"):
        cx, cy, r = CARD_W - 58, CARD_H // 2 + 6, 27
        a(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c["RING_BG"]}" '
          f'stroke-width="9" stroke-dasharray="3 5"/>')
        s = 20 / 16
        a(f'<g transform="translate({cx-10},{cy-10}) scale({s:.3f})" fill="{c["DIM"]}">'
          f'<path d="{ICON_LOCK}"/></g>')

    a('</g>')
    a('</a>')
    return "".join(e)


def build(projects, theme, logos_dir):
    c = THEMES[theme]
    rows = math.ceil(len(projects) / 2)
    height = 56 + rows * (CARD_H + GAP) + MARGIN
    gid = f"acc_{theme}"
    s = []
    a = s.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
      f'viewBox="0 0 {W} {height}" font-family="{FONT}" role="img" aria-label="Projects">')
    a(f'<rect width="{W}" height="{height}" fill="{c["BG"]}"/>')
    a(f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
      f'<stop offset="0" stop-color="{c["GOLD"]}"><animate attributeName="stop-color" '
      f'values="{c["GOLD"]};{c["EMERALD"]};{c["GOLD"]}" dur="10s" repeatCount="indefinite"/></stop>'
      f'<stop offset="1" stop-color="{c["EMERALD"]}"><animate attributeName="stop-color" '
      f'values="{c["EMERALD"]};{c["GOLD"]};{c["EMERALD"]}" dur="10s" repeatCount="indefinite"/></stop>'
      '</linearGradient></defs>')
    a(f'<text x="{MARGIN+2}" y="18" font-size="11" letter-spacing="2" fill="{c["GOLD"]}">PROJECTS.LIST</text>')
    a(f'<text x="{MARGIN+140}" y="18" font-size="10" fill="{c["DIM"]}">./projects.sh --all</text>')
    a(f'<line x1="{MARGIN}" y1="28" x2="{W-MARGIN}" y2="28" stroke="url(#{gid})" stroke-width="1.5" opacity="0.7"/>')
    for i, p in enumerate(projects):
        x = MARGIN + (i % 2) * (CARD_W + GAP + 4)
        y = 42 + (i // 2) * (CARD_H + GAP)
        a(card(p, x, y, i, c, logos_dir))
    a('</svg>')
    return "".join(s)


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/merged.json")
    outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "assets")
    logos_dir = Path(sys.argv[3] if len(sys.argv) > 3 else "logos")
    projects = json.loads(src.read_text(encoding="utf-8"))
    outdir.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = build(projects, theme, logos_dir)
        path = outdir / (f"projects-{theme}.svg")
        path.write_text(svg, encoding="utf-8")
        print(f"wrote {path}: {theme}, {len(projects)} projects, {len(svg)//1024}KB")


if __name__ == "__main__":
    main()
