#!/usr/bin/env python3
"""
hero.py - render the profile hero banner: a "luxury terminal" window with a
dot-matrix portrait (built from a real photo via lib/portrait.py) on the
left and a typed system readout on the right.

    python3 scripts/hero.py --photo assets/hemansh-face-source.png \
        --focus 0.5,0.35 -o assets

Writes <out>/hero-dark.svg and <out>/hero-light.svg. Pure SMIL animation
(<animate>/<animateTransform>) - no <script>, no external calls at render
time, so it renders identically wherever GitHub displays it.

All copy (name, role, bio, stack, location) lives in the CONTENT dict below
-- edit it directly, there is no separate data file, because none of this
text is meant to be machine-generated.
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.portrait import circle_falloff, load_grid  # noqa: E402

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
CHAR_W = 0.6  # advance width of the mono stack above, as a fraction of font-size

# ----------------------------------------------------------------------- #
# palette - dark luxury: near-black + off-white + emerald + champagne gold
# ----------------------------------------------------------------------- #
THEMES = {
    "dark": {
        "bg": "#08090A", "panel": "#0F1012", "panel_bar": "#0C0D0E",
        "border": "rgba(212,175,55,0.22)", "border_hi": "rgba(16,185,129,0.55)",
        "text": "#F5F5F4", "muted": "#9CA3AF", "dim": "#52525B",
        "emerald": "#10B981", "gold": "#D4AF37", "line": "rgba(255,255,255,0.08)",
        "ink": "#E8E6DF", "ink_dim": "#2A2A2C",
    },
    "light": {
        "bg": "#FAFAF9", "panel": "#FFFFFF", "panel_bar": "#F4F4F3",
        "border": "rgba(180,140,20,0.28)", "border_hi": "rgba(5,150,105,0.55)",
        "text": "#101012", "muted": "#52525B", "dim": "#9CA3AF",
        "emerald": "#059669", "gold": "#A67C00", "line": "rgba(0,0,0,0.08)",
        "ink": "#17181A", "ink_dim": "#D6D3CE",
    },
}

W, H = 1200, 620


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# ----------------------------------------------------------------------- #
# typing effect: reveal a monospace string with a clip-path sweep, then
# leave a blinking cursor at the end. Purely SMIL, works as a static <img>.
# ----------------------------------------------------------------------- #
_uid = [0]


def typed_text(x, y, text, size, color, begin, cps=26, weight="600",
                cursor=False, cursor_color=None, char_w=None):
    _uid[0] += 1
    cid = f"tc{_uid[0]}"
    text_w = len(text) * size * (char_w or CHAR_W) + 8
    dur = max(len(text) / cps, 0.05)
    out = [
        f'<clipPath id="{cid}"><rect x="{x - 2:.1f}" y="{y - size:.1f}" '
        f'width="0" height="{size * 1.5:.1f}">'
        f'<animate attributeName="width" from="0" to="{text_w + 4:.1f}" '
        f'dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/>'
        f'</rect></clipPath>',
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" clip-path="url(#{cid})">{esc(text)}</text>',
    ]
    if cursor:
        cc = cursor_color or color
        cx = x + text_w + 2
        out.append(
            f'<rect x="{cx:.1f}" y="{y - size * 0.82:.1f}" width="{size * 0.52:.1f}" '
            f'height="{size * 1.05:.1f}" fill="{cc}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;1;0;1" '
            f'keyTimes="0;{min(begin / (begin + dur + 2), 0.98):.3f};'
            f'{min((begin + dur) / (begin + dur + 2), 0.99):.3f};'
            f'{min((begin + dur + 0.5) / (begin + dur + 2), 0.995):.3f};1" '
            f'dur="{begin + dur + 2:.2f}s" begin="0s" repeatCount="indefinite"/>'
            f'</rect>'
        )
    return "".join(out), begin + dur


def fade_line(x, y, text, size, color, begin, dur=0.5, weight="400", anchor="start"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" text-anchor="{anchor}" opacity="0">{esc(text)}'
        f'<animate attributeName="opacity" from="0" to="1" dur="{dur}s" '
        f'begin="{begin:.2f}s" fill="freeze"/></text>'
    )


def tag_pill(x, y, label, c, begin):
    tw = len(label) * 6.4 + 16
    body = (
        f'<g transform="translate({x:.1f},{y:.1f})" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
        f'<rect width="{tw:.0f}" height="22" rx="11" fill="rgba(16,185,129,0.10)" '
        f'stroke="{c["emerald"]}" stroke-opacity="0.4"/>'
        f'<text x="{tw/2:.0f}" y="15" text-anchor="middle" font-size="11" '
        f'font-weight="600" fill="{c["ink"]}">{esc(label)}</text>'
        f'</g>'
    )
    return body, tw


# ----------------------------------------------------------------------- #
# portrait panel (mono ink, matches terminal theme rather than skin tones)
# ----------------------------------------------------------------------- #

def portrait_dots(photo, focus, panel_w, panel_h, c, cols=78):
    fx, fy = focus
    cols_i, rows_i, lum, _ = load_grid(photo, cols, contrast=1.38, gamma=1.0,
                                       cell_aspect=1.0, square=True,
                                       focus=(fx, fy), equalize=False, detail=0.6)
    cell = panel_w / cols_i
    max_r = cell * 0.5 * 0.92
    out = []
    for y in range(rows_i):
        for x in range(cols_i):
            v = 1 - lum[y][x]  # invert: subject is darker than the sky behind it
            v *= circle_falloff(x, y, cols_i, rows_i, feather=0.08)
            if v < 0.045:
                continue
            r = max_r * v
            cx = x * cell + cell / 2
            cy = y * cell + cell / 2
            fill = c["ink"] if v > 0.30 else c["ink_dim"]
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" fill="{fill}"/>')
    return "".join(out), rows_i * cell


# ----------------------------------------------------------------------- #
# build
# ----------------------------------------------------------------------- #

def build(theme, photo, focus, content):
    c = THEMES[theme]
    s = []
    a = s.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
      f'aria-label="{esc(content["name"])} - {esc(content["role"])}">')

    a('<defs>')
    a(f'<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">'
      f'<stop offset="0" stop-color="{c["gold"]}"><animate attributeName="stop-color" '
      f'values="{c["gold"]};{c["emerald"]};{c["gold"]}" dur="12s" repeatCount="indefinite"/></stop>'
      f'<stop offset="1" stop-color="{c["emerald"]}"><animate attributeName="stop-color" '
      f'values="{c["emerald"]};{c["gold"]};{c["emerald"]}" dur="12s" repeatCount="indefinite"/></stop>'
      f'</linearGradient>')
    a(f'<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">'
      f'<stop offset="0" stop-color="{c["panel"]}"/><stop offset="1" stop-color="{c["bg"]}"/>'
      f'</linearGradient>')
    a(f'<clipPath id="winclip"><rect x="1" y="1" width="{W-2}" height="{H-2}" rx="20"/></clipPath>')
    a(f'<clipPath id="portraitclip"><rect x="0" y="0" width="420" height="{H-92}" rx="14"/></clipPath>')
    a('</defs>')

    # outer glow border + shell
    a(f'<rect x="0.75" y="0.75" width="{W-1.5}" height="{H-1.5}" rx="20" fill="none" '
      f'stroke="url(#edge)" stroke-width="1.5" opacity="0.75"/>')
    a('<g clip-path="url(#winclip)">')
    a(f'<rect width="{W}" height="{H}" fill="url(#sheen)"/>')

    # title bar
    a(f'<rect x="1" y="1" width="{W-2}" height="46" fill="{c["panel_bar"]}"/>')
    a(f'<line x1="1" y1="47" x2="{W-1}" y2="47" stroke="{c["line"]}"/>')
    for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        a(f'<circle cx="{30+i*20}" cy="24" r="5.5" fill="{col}" opacity="0.9"/>')
    a(f'<text x="{W/2}" y="28" text-anchor="middle" font-size="12" fill="{c["muted"]}">'
      f'hemansh@systems:~% ./whoami.sh --live</text>')
    a(f'<text x="{W-24}" y="28" text-anchor="end" font-size="10" letter-spacing="2" '
      f'fill="{c["gold"]}">SYSTEMS.ARCHITECT</text>')

    body_top = 47
    pad = 30

    # ---------------- left: portrait panel ----------------
    px, py = pad, body_top + 22
    pw, ph = 420, H - body_top - 44
    a(f'<g transform="translate({px},{py})">')
    a(f'<rect width="{pw}" height="{ph}" rx="14" fill="{c["bg"]}" stroke="{c["border"]}"/>')
    a(f'<text x="16" y="24" font-size="10" letter-spacing="3" fill="{c["dim"]}">VISUAL.MAP</text>')
    a(f'<line x1="16" y1="34" x2="{pw-16}" y2="34" stroke="{c["line"]}"/>')
    a('<g clip-path="url(#portraitclip)" transform="translate(10,44)">')
    dots, used_h = portrait_dots(photo, focus, pw - 20, ph - 60, c)
    a(dots)
    a('</g>')
    a(f'<text x="16" y="{ph-16}" font-size="10" fill="{c["dim"]}">'
      f'{content["location"]} <tspan fill="{c["emerald"]}">&#8226;</tspan> {content["status"]}</text>')
    a('</g>')

    # ---------------- right: system info ----------------
    rx = px + pw + 34
    rw = W - rx - pad
    ry = body_top + 30
    a(f'<text x="{rx}" y="{ry}" font-size="10" letter-spacing="3" fill="{c["dim"]}">SYSTEM.INFO</text>')
    a(f'<line x1="{rx}" y1="{ry+10}" x2="{W-pad}" y2="{ry+10}" stroke="url(#edge)" stroke-width="1" opacity="0.6"/>')

    t = ry + 58
    name_svg, t_end = typed_text(rx, t, content["name"], 42, c["text"], begin=0.15, cps=14, weight="800", cursor=True, cursor_color=c["emerald"], char_w=0.68)
    a(name_svg)

    t2 = t + 38
    role_svg, t2_end = typed_text(rx, t2, content["role"], 17, c["gold"], begin=t_end + 0.15, cps=32, weight="600")
    a(role_svg)

    y = t2 + 44
    a(f'<text x="{rx}" y="{y}" font-size="11" fill="{c["emerald"]}" opacity="0">$ cat about.txt'
      f'<animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{t2_end+0.3:.2f}s" fill="freeze"/></text>')
    y += 22
    for i, line in enumerate(content["bio"]):
        a(fade_line(rx, y, line, 12.5, c["muted"], t2_end + 0.5 + i * 0.35, weight="400"))
        y += 20

    y += 12
    stack_begin = t2_end + 0.5 + len(content["bio"]) * 0.35 + 0.3
    a(f'<text x="{rx}" y="{y}" font-size="11" fill="{c["emerald"]}" opacity="0">$ ./stack --list'
      f'<animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{stack_begin:.2f}s" fill="freeze"/></text>')
    y += 16
    tx = rx
    ty = y + 14
    row_start = tx
    for i, tag in enumerate(content["stack"]):
        pill, tw = tag_pill(tx, ty, tag, c, stack_begin + 0.25 + i * 0.12)
        if tx + tw > rx + rw:
            tx = row_start
            ty += 32
            pill, tw = tag_pill(tx, ty, tag, c, stack_begin + 0.25 + i * 0.12)
        a(pill)
        tx += tw + 10

    footer_begin = stack_begin + 0.25 + len(content["stack"]) * 0.12 + 0.4
    fy = H - 30
    a(f'<line x1="{rx}" y1="{fy-24}" x2="{W-pad}" y2="{fy-24}" stroke="{c["line"]}"/>')
    a(f'<text x="{rx}" y="{fy}" font-size="11" fill="{c["dim"]}" opacity="0">building: '
      f'<tspan fill="{c["text"]}">{esc(content["building"])}</tspan>'
      f'<animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{footer_begin:.2f}s" fill="freeze"/></text>')
    a(f'<circle cx="{W-pad-6}" cy="{fy-4}" r="4" fill="{c["emerald"]}" opacity="0">'
      f'<animate attributeName="opacity" values="0;1;0.3;1" dur="1.8s" begin="{footer_begin:.2f}s" repeatCount="indefinite"/></circle>')

    a('</g>')  # winclip
    a('</svg>')
    return "".join(s)


CONTENT = {
    "name": "Hemansh",
    "role": "Systems Architect / Polymath",
    "location": "Bihar, IN",
    "status": "shipping",
    "bio": [
        "Built a kernel from scratch, a browser, a GPU compute engine,",
        "and the backend for a social app. If it's close to the metal,",
        "I probably want to build it.",
    ],
    "stack": ["Python", "C", "C++", "Java", "React", "Go"],
    "building": "V.I.N.C.E. -- an OS kernel, from bare metal up",
}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--photo", type=Path, default=Path("assets/hemansh-face-source.png"))
    p.add_argument("--focus", default="0.5,0.35")
    p.add_argument("-o", "--out", type=Path, default=Path("assets"))
    args = p.parse_args(argv)

    if not args.photo.exists():
        sys.exit(f"no such image: {args.photo}")
    fx, fy = (float(v) for v in args.focus.split(","))

    args.out.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = build(theme, args.photo, (fx, fy), CONTENT)
        dest = args.out / f"hero-{theme}.svg"
        dest.write_text(svg, encoding="utf-8")
        print(f"wrote {dest}  ({len(svg)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
