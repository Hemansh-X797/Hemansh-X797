#!/usr/bin/env python3
"""
radar.py - render an animated hexagon radar chart. Two data sources:

  1. hand-rated, from data/skills.json (default)
        python3 scripts/radar.py -o assets

  2. live language mix, summed from real byte counts across your repos
        python3 scripts/radar.py --github Hemansh-X797 -o assets/radar-langs

Writes <out>-dark.svg and <out>-light.svg (or <out>/radar-{theme}.svg when
-o is a directory, matching the first form above). Geometry is computed
from however many axes are in the data -- add/remove entries in
skills.json and the hexagon becomes a pentagon/heptagon/etc. automatically.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
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
UA = {"User-Agent": "radar.py"}


def point(angle, r):
    return CX + r * math.sin(angle), CY - r * math.cos(angle)


def build(theme, axes, title):
    c = THEMES[theme]
    n = len(axes)
    step = 2 * math.pi / n

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="ui-monospace,SFMono-Regular,Menlo,'
         f'Consolas,monospace" role="img" aria-label="{title}">']
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
              f'letter-spacing="3" fill="{c["muted"]}">{title}</text>')

    for ring in range(1, RINGS + 1):
        rr = R * ring / RINGS
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in
                       (point(i * step, rr) for i in range(n)))
        s.append(f'<polygon points="{pts}" fill="none" stroke="{c["grid"]}" stroke-width="1"/>')
    for i in range(n):
        x, y = point(i * step, R)
        s.append(f'<line x1="{CX}" y1="{CY}" x2="{x:.1f}" y2="{y:.1f}" '
                  f'stroke="{c["grid"]}" stroke-width="1"/>')

    data_pts = [point(i * step, R * axes[i]["value"] / 100) for i in range(n)]
    pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)
    perim = sum(
        math.hypot(data_pts[i][0] - data_pts[(i + 1) % n][0],
                   data_pts[i][1] - data_pts[(i + 1) % n][1])
        for i in range(n)
    )
    s.append(f'<polygon points="{pts_str}" fill="{c["fill"]}" stroke="{c["stroke"]}" '
              f'stroke-width="2.5" stroke-linejoin="round" class="poly" '
              f'style="--len:{perim:.1f}"/>')

    for i, ax in enumerate(axes):
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
                  f'style="animation-delay:{0.9 + i * 0.05:.2f}s">{ax["label"]}</text>')
        s.append(f'<text x="{lx:.1f}" y="{ly + 15:.1f}" text-anchor="{anchor}" '
                  f'font-size="10" fill="{c["muted"]}" class="lbl" '
                  f'style="animation-delay:{0.95 + i * 0.05:.2f}s">{ax["value"]:g}%</text>')

    s.append('</svg>')
    return "".join(s)


# --------------------------------------------------------------------------- #
# data sources
# --------------------------------------------------------------------------- #

def from_json(path: Path):
    axes = json.loads(path.read_text(encoding="utf-8"))["skills"]
    return "SKILL.MATRIX", axes


def _api(url, token):
    req = urllib.request.Request(url, headers=dict(UA))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def from_github(user, token, limit, exclude, curve):
    """Sum language bytes across the user's non-fork public repos. Private
    repos need a token to show up here at all."""
    totals: dict[str, int] = {}
    page = 1
    while True:
        repos = _api(
            f"https://api.github.com/users/{user}/repos"
            f"?per_page=100&page={page}&type=owner&sort=pushed", token)
        if not repos:
            break
        for repo in repos:
            if repo.get("fork") or repo.get("archived"):
                continue
            try:
                langs = _api(repo["languages_url"], token)
            except urllib.error.HTTPError:
                continue
            for name, count in langs.items():
                if name.lower() in exclude:
                    continue
                totals[name] = totals.get(name, 0) + count
        if len(repos) < 100:
            break
        page += 1

    if not totals:
        sys.exit(f"no language data found for '{user}' (private repos need a token)")

    top = sorted(totals.items(), key=lambda kv: -kv[1])[:limit]
    peak = top[0][1]
    # raw byte ratios are lopsided -- one dominant language pins every other
    # axis near the centre. curve compresses that: 1.0 linear, 0.5 sqrt.
    axes = [{"label": n, "value": round(100 * (v / peak) ** curve, 1)} for n, v in top]
    return "LANGUAGE.MIX", axes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--data", type=Path, default=Path("data/skills.json"))
    src.add_argument("--github", metavar="USER",
                     help="build the radar from live GitHub language bytes instead")
    p.add_argument("-o", "--out", type=Path, default=Path("assets/radar"),
                   help="output path WITHOUT extension, e.g. assets/radar or assets/radar-langs")
    p.add_argument("--title", help="override the chart title")
    p.add_argument("--limit", type=int, default=6, help="max axes in --github mode")
    p.add_argument("--curve", type=float, default=0.5,
                   help="--github axis scaling: 1.0 linear, 0.5 sqrt (default)")
    p.add_argument("--exclude", default="html,css,shell,makefile,dockerfile,batchfile",
                   help="comma-separated languages to skip in --github mode")
    args = p.parse_args(argv)

    if args.github:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        excl = {s.strip().lower() for s in args.exclude.split(",") if s.strip()}
        title, axes = from_github(args.github, token, args.limit, excl, args.curve)
    else:
        if not args.data.exists():
            sys.exit(f"no such file: {args.data}")
        title, axes = from_json(args.data)
    if args.title is not None:
        title = args.title
    if len(axes) < 3:
        sys.exit("need at least 3 axes to draw a radar")

    # -o is a path stem WITHOUT extension, e.g. "assets/radar" or
    # "assets/radar-langs" -- writes <stem>-dark.svg / <stem>-light.svg.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = build(theme, axes, title)
        dest = args.out.with_name(f"{args.out.name}-{theme}.svg")
        dest.write_text(svg, encoding="utf-8")
        print(f"wrote {dest}  ({len(axes)} axes)")


if __name__ == "__main__":
    main()
