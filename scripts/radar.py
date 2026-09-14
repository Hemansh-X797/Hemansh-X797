#!/usr/bin/env python3
"""
radar.py - render an animated skills radar chart from data/skills.json.

    python3 scripts/radar.py -o assets

Writes <out>/radar-dark.svg and <out>/radar-light.svg. The chart geometry
(polygon, spokes, tick rings) is computed from whatever is in skills.json --
add or remove entries there and the layout adapts; nothing about the shape
is hardcoded to six axes.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

W, H = 480, 500
CX, CY = W / 2, H / 2 + 6
R = 150
RINGS = 4

THEMES = {
    "dark": {
        "bg": "#08090A", "grid": "rgba(255,255,255,0.10)",
        "text": "#F5F5F4", "muted": "#8B8B90",
        "fill": "rgba(16,185,129,0.22)", "stroke": "#10B981", "dot": "#D4AF37",
    },
    "light": {
        "bg": "#FAFAF9", "grid": "rgba(0,0,0,0.10)",
        "text": "#101012", "muted": "#6B6B70",
        "fill": "rgba(5,150,105,0.18)", "stroke": "#059669", "dot": "#A67C00",
    },
}


def point(angle, r):
    return CX + r * math.sin(angle), CY - r * math.cos(angle)


def build(theme, skills):
    c = THEMES[theme]
    n = len(skills)
    step = 2 * math.pi / n

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Menlo,'
         f'Consolas,monospace" role="img" aria-label="skills radar">']
    s.append(
        '<style>'
        '@keyframes drawpoly{from{stroke-dashoffset:var(--len)}to{stroke-dashoffset:0}}'
        '.poly{stroke-dasharray:var(--len);animation:drawpoly 1.4s ease-out forwards}'
        '@keyframes popin{from{opacity:0;transform:scale(0)}to{opacity:1;transform:scale(1)}}'
        '.node{opacity:0;animation:popin .4s ease-out forwards;transform-box:fill-box;'
        'transform-origin:center}'
        '@keyframes fadein{from{opacity:0}to{opacity:1}}'
        '.lbl{opacity:0;animation:fadein .5s ease-out forwards}'
        '</style>'
    )
    s.append(f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>')
    s.append(f'<text x="{W/2}" y="30" text-anchor="middle" font-size="12" '
              f'letter-spacing="3" fill="{c["muted"]}">SKILL.MATRIX</text>')

    # ring grid + spokes
    for ring in range(1, RINGS + 1):
        rr = R * ring / RINGS
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                       (point(i * step, rr) for i in range(n)))
        s.append(f'<polygon points="{pts}" fill="none" stroke="{c["grid"]}" stroke-width="1"/>')
    for i in range(n):
        x, y = point(i * step, R)
        s.append(f'<line x1="{CX}" y1="{CY}" x2="{x:.1f}" y2="{y:.1f}" '
                  f'stroke="{c["grid"]}" stroke-width="1"/>')

    # data polygon
    data_pts = [point(i * step, R * skills[i]["value"] / 100) for i in range(n)]
    pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)
    # approximate perimeter length for the dash-draw animation
    perim = sum(
        math.hypot(data_pts[i][0] - data_pts[(i + 1) % n][0],
                   data_pts[i][1] - data_pts[(i + 1) % n][1])
        for i in range(n)
    )
    s.append(f'<polygon points="{pts_str}" fill="{c["fill"]}" stroke="{c["stroke"]}" '
              f'stroke-width="2.5" stroke-linejoin="round" class="poly" '
              f'style="--len:{perim:.1f}"/>')

    # value nodes + axis labels
    for i, sk in enumerate(skills):
        x, y = data_pts[i]
        delay = 1.1 + i * 0.08
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{c["dot"]}" '
                  f'class="node" style="animation-delay:{delay:.2f}s"/>')

        lx, ly = point(i * step, R + 34)
        anchor = "middle"
        if math.sin(i * step) > 0.35:
            anchor = "start"
        elif math.sin(i * step) < -0.35:
            anchor = "end"
        s.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                  f'font-size="13" font-weight="700" fill="{c["text"]}" class="lbl" '
                  f'style="animation-delay:{0.9 + i * 0.05:.2f}s">{sk["label"]}</text>')
        s.append(f'<text x="{lx:.1f}" y="{ly + 15:.1f}" text-anchor="{anchor}" '
                  f'font-size="10" fill="{c["muted"]}" class="lbl" '
                  f'style="animation-delay:{0.95 + i * 0.05:.2f}s">{sk["value"]}%</text>')

    s.append('</svg>')
    return "".join(s)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data/skills.json"))
    p.add_argument("-o", "--out", type=Path, default=Path("assets"))
    args = p.parse_args(argv)

    if not args.data.exists():
        sys.exit(f"no such file: {args.data}")
    skills = json.loads(args.data.read_text())["skills"]
    if len(skills) < 3:
        raise SystemExit("need at least 3 skills to draw a radar")

    args.out.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = build(theme, skills)
        dest = args.out / f"radar-{theme}.svg"
        dest.write_text(svg, encoding="utf-8")
        print(f"wrote {dest}  ({len(svg)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
