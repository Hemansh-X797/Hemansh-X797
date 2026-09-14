#!/usr/bin/env python3
"""
dotify.py - turn a photo into dot-matrix / binary-grid art as an SVG.

Usage
-----
    python3 scripts/dotify.py assets/hemansh-face-source.png -o assets/portrait \
        --cols 130 --square --focus 0.5,0.35 --detail 0.6 --contrast 1.35 \
        --color --invert --circle --reveal

Writes <out>.svg (color mode) or <out>-dark.svg / <out>-light.svg (mono mode).
Also writes <out>.txt for the text modes (ascii/braille).

Note on --invert: a face lit against a bright sky is DARKER than its
background, so a plain brightness->dot-size mapping fills in the sky and
leaves the face empty. --invert flips that so the subject gets the ink.
Use it whenever the background is brighter than the subject.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.portrait import circle_falloff, load_grid  # noqa: E402

try:
    import PIL  # noqa: F401
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required:  python3 -m pip install Pillow")

THEMES = {
    "dark": ("#22D3EE", "#164E63"),
    "light": ("#0891B2", "#A5F3FC"),
}
ASCII_RAMP = "@%#*+=-:. "
BRAILLE_BASE = 0x2800
BRAILLE_BITS = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]]


def svg_header(w, h, rows, opts):
    css = []
    if opts.animate:
        css.append("@keyframes dp{0%,100%{opacity:.45}50%{opacity:1}}")
        css.append(f".d{{animation:dp {opts.duration}s ease-in-out infinite}}")
        css += [f".l{i}{{animation-delay:{i / opts.lanes * opts.duration:.2f}s}}"
                for i in range(opts.lanes)]
    if opts.reveal:
        step = opts.reveal_time / max(rows - 1, 1)
        css.append("@keyframes rv{from{opacity:0}to{opacity:1}}")
        css.append(f".rw{{animation:rv {opts.reveal_fade}s ease-out both}}")
        css += [
            f".r{y}{{animation-delay:{(rows - 1 - y if opts.reveal_dir == 'up' else y) * step:.3f}s}}"
            for y in range(rows)
        ]
    style = f"<style>{''.join(css)}</style>" if css else ""
    bgrect = f'<rect width="100%" height="100%" fill="{opts.bg}"/>' if opts.bg else ""
    pad = opts.pad
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w + 2 * pad} {h + 2 * pad}" '
        f'width="{w + 2 * pad}" height="{h + 2 * pad}" role="img" '
        f'aria-label="dot-matrix portrait">{style}{bgrect}'
        f'<g transform="translate({pad},{pad})">'
    )


def build_dots(cols, rows, lum, rgb, theme, opts):
    fg, dim = THEMES[theme]
    cell = opts.cell
    max_r = cell * 0.5 * opts.dot_scale
    lanes = opts.lanes
    out = []
    for y in range(rows):
        row = []
        for x in range(cols):
            v = lum[y][x]
            if opts.invert:
                v = 1 - v
            if opts.circle:
                v *= circle_falloff(x, y, cols, rows)
            if v < opts.floor:
                continue
            r = max_r * v
            if opts.color:
                cr, cg, cb = rgb[y][x]
                fill = f"#{cr:02x}{cg:02x}{cb:02x}"
            else:
                fill = fg if v > 0.42 else dim
            cx = x * cell + cell / 2
            cy = y * cell + cell / 2
            cls = f' class="d l{x % lanes}"' if opts.animate else ""
            row.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" fill="{fill}"{cls}/>')
        if not row:
            continue
        if opts.reveal:
            out.append(f'<g class="rw r{y}">{"".join(row)}</g>')
        else:
            out += row
    return "".join(out), cols * cell, rows * cell


def build_binary(cols, rows, lum, rgb, theme, opts):
    fg, dim = THEMES[theme]
    cell = opts.cell
    lanes = opts.lanes
    out = [
        f'<g font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
        f'font-size="{cell * 0.92:.2f}" text-anchor="middle">'
    ]
    for y in range(rows):
        row = []
        for x in range(cols):
            v = lum[y][x]
            if opts.invert:
                v = 1 - v
            if opts.circle:
                v *= circle_falloff(x, y, cols, rows)
            if v < opts.floor:
                continue
            bit = "1" if ((x * 7 + y * 13 + int(v * 37)) % 3) else "0"
            if v > 0.62:
                bit = "1"
            if opts.color:
                cr, cg, cb = rgb[y][x]
                fill = f"#{cr:02x}{cg:02x}{cb:02x}"
            else:
                fill = fg if v > 0.42 else dim
            cls = f' class="d l{x % lanes}"' if opts.animate else ""
            op = f' opacity="{0.25 + 0.75 * v:.2f}"'
            row.append(
                f'<text x="{x * cell + cell / 2:.1f}" y="{y * cell + cell * 0.82:.1f}" '
                f'fill="{fill}"{op}{cls}>{bit}</text>'
            )
        if not row:
            continue
        if opts.reveal:
            out.append(f'<g class="rw r{y}">{"".join(row)}</g>')
        else:
            out += row
    out.append("</g>")
    return "".join(out), cols * cell, rows * cell


def build_ascii(cols, rows, lum, opts):
    lines = []
    n = len(ASCII_RAMP) - 1
    for y in range(rows):
        row = []
        for x in range(cols):
            v = lum[y][x]
            if opts.invert:
                v = 1 - v
            if opts.circle:
                v *= circle_falloff(x, y, cols, rows)
            row.append(ASCII_RAMP[n - min(n, int(v * n + 0.5))])
        lines.append("".join(row).rstrip())
    return "\n".join(lines)


def build_braille(cols, rows, lum, opts):
    lines = []
    for by in range(0, rows - 3, 4):
        row = []
        for bx in range(0, cols - 1, 2):
            bits = 0
            for dy in range(4):
                for dx in range(2):
                    v = lum[by + dy][bx + dx]
                    if opts.invert:
                        v = 1 - v
                    if opts.circle:
                        v *= circle_falloff(bx + dx, by + dy, cols, rows)
                    if v > opts.threshold:
                        bits |= BRAILLE_BITS[dy][dx]
            row.append(chr(BRAILLE_BASE + bits))
        lines.append("".join(row).rstrip())
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", type=Path)
    p.add_argument("-o", "--out", type=Path, default=Path("assets/portrait"))
    p.add_argument("--mode", choices=("dots", "binary", "ascii", "braille"), default="dots")
    p.add_argument("--cols", type=int, default=100)
    p.add_argument("--cell", type=float, default=10.0)
    p.add_argument("--dot-scale", type=float, default=0.92)
    p.add_argument("--gamma", type=float, default=1.0)
    p.add_argument("--contrast", type=float, default=1.25)
    p.add_argument("--equalize", action="store_true")
    p.add_argument("--detail", type=float, default=0.0)
    p.add_argument("--floor", type=float, default=0.06)
    p.add_argument("--threshold", type=float, default=0.45)
    p.add_argument("--cell-aspect", type=float, default=1.0)
    p.add_argument("--square", action="store_true")
    p.add_argument("--focus", default="0.5,0.5")
    p.add_argument("--invert", action="store_true")
    p.add_argument("--circle", action="store_true")
    p.add_argument("--color", action="store_true")
    p.add_argument("--animate", action="store_true")
    p.add_argument("--lanes", type=int, default=14)
    p.add_argument("--duration", type=float, default=4.0)
    p.add_argument("--reveal", action="store_true")
    p.add_argument("--reveal-time", type=float, default=2.5)
    p.add_argument("--reveal-fade", type=float, default=0.45)
    p.add_argument("--reveal-dir", choices=("down", "up"), default="down")
    p.add_argument("--pad", type=float, default=8.0)
    p.add_argument("--bg", default="")
    args = p.parse_args(argv)

    if args.mode == "ascii" and args.cell_aspect == 1.0:
        args.cell_aspect = 0.5

    if not args.image.exists():
        sys.exit(f"no such image: {args.image}")

    try:
        fx, fy = (float(v) for v in args.focus.split(","))
    except ValueError:
        sys.exit(f"--focus wants two numbers like 0.5,0.35 (got {args.focus!r})")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    cols, rows, lum, rgb = load_grid(args.image, args.cols, args.contrast,
                                     args.gamma, args.cell_aspect,
                                     args.square, (fx, fy),
                                     args.equalize, args.detail)

    if args.mode in ("ascii", "braille"):
        text = (build_ascii if args.mode == "ascii" else build_braille)(cols, rows, lum, args)
        txt = args.out.with_suffix(".txt")
        txt.write_text(text, encoding="utf-8")
        print(f"wrote {txt}  ({cols}x{rows} cells)")
        return

    builder = build_dots if args.mode == "dots" else build_binary
    themes = ("dark",) if args.color else ("dark", "light")
    for theme in themes:
        body, w, h = builder(cols, rows, lum, rgb, theme, args)
        svg = svg_header(w, h, rows, args) + body + "</g></svg>"
        stem = args.out.name if args.color else f"{args.out.name}-{theme}"
        dest = args.out.with_name(f"{stem}.svg")
        dest.write_text(svg, encoding="utf-8")
        print(f"wrote {dest}  ({len(svg) / 1024:.0f} KB, {cols}x{rows} cells)")


if __name__ == "__main__":
    main()
