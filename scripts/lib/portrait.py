"""
Shared photo -> luminance/rgb grid sampler.

Used by both dotify.py (standalone portrait art) and hero.py (the terminal
banner, which embeds a smaller version of the same dot-matrix portrait).
Keeping one implementation means a fix or a look change made in one place
is guaranteed to apply everywhere the photo gets rendered.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


def square_crop(img, fx: float, fy: float):
    """Crop to 1:1 around a focus point given in 0..1 image coordinates."""
    w, h = img.size
    side = min(w, h)
    left = min(max(fx * w - side / 2, 0), w - side)
    top = min(max(fy * h - side / 2, 0), h - side)
    return img.crop((round(left), round(top), round(left) + side, round(top) + side))


def load_grid(path: Path, cols: int, contrast: float = 1.25, gamma: float = 1.0,
              cell_aspect: float = 1.0, square: bool = False,
              focus: tuple[float, float] = (0.5, 0.5),
              equalize: bool = False, detail: float = 0.0):
    """Return (cols, rows, lum[y][x] in 0..1, rgb[y][x])."""
    img = ImageOps.exif_transpose(Image.open(path))

    mask = None
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        if img.split()[3].getextrema()[0] < 250:
            mask = img.split()[3]
        flat = Image.new("RGBA", img.size, (0, 0, 0, 255))
        flat.alpha_composite(img)
        img = flat
    img = img.convert("RGB")

    if square:
        img = square_crop(img, *focus)
        if mask is not None:
            mask = square_crop(mask, *focus)

    gray = img.convert("L")

    if equalize:
        binmask = mask.point(lambda v: 255 if v > 127 else 0) if mask else None
        gray = ImageOps.equalize(gray, mask=binmask)
    if detail > 0:
        radius = max(2, round(min(img.size) / 52))
        gray = gray.filter(ImageFilter.UnsharpMask(
            radius=radius, percent=round(detail * 100), threshold=0))
    if contrast != 1.0:
        gray = ImageEnhance.Contrast(gray).enhance(contrast)
        img = ImageEnhance.Contrast(img).enhance(contrast)

    w, h = img.size
    rows = max(1, round(cols * (h / w) * cell_aspect))
    small_g = gray.resize((cols, rows), Image.Resampling.LANCZOS)
    if mask is not None:
        small_m = mask.resize((cols, rows), Image.Resampling.LANCZOS)
        small_g = ImageChops.multiply(small_g, small_m)
    small_c = img.resize((cols, rows), Image.Resampling.LANCZOS)

    gp, cp = small_g.load(), small_c.load()
    rgb, lum = [], []
    for y in range(rows):
        rgb_row, lum_row = [], []
        for x in range(cols):
            rgb_row.append(cp[x, y])
            v = gp[x, y] / 255.0
            lum_row.append(min(1.0, max(0.0, v ** gamma)))
        rgb.append(rgb_row)
        lum.append(lum_row)
    return cols, rows, lum, rgb


def circle_falloff(x, y, cols, rows, feather=0.06):
    """1 inside the inscribed circle, fading to 0 just outside it."""
    nx = (x + 0.5) / cols * 2 - 1
    ny = (y + 0.5) / rows * 2 - 1
    d = math.hypot(nx, ny)
    if d <= 1 - feather:
        return 1.0
    if d >= 1 + feather:
        return 0.0
    return (1 + feather - d) / (2 * feather)


def dot_grid_svg(cols, rows, lum, rgb, *, cell, max_dot_scale=0.92, invert=False,
                  circle=False, color=False, floor=0.045, mono_fg="#22D3EE",
                  mono_dim="#1E293B", reveal=False, reveal_time=2.2,
                  reveal_fade=0.4, class_prefix="p"):
    """Render a luminance grid as halftone <circle> dots. Returns (body, w, h)."""
    max_r = cell * 0.5 * max_dot_scale
    out = []
    for y in range(rows):
        row = []
        for x in range(cols):
            v = lum[y][x]
            if invert:
                v = 1 - v
            if circle:
                v *= circle_falloff(x, y, cols, rows)
            if v < floor:
                continue
            r = max_r * v
            if color:
                cr, cg, cb = rgb[y][x]
                fill = f"#{cr:02x}{cg:02x}{cb:02x}"
            else:
                fill = mono_fg if v > 0.42 else mono_dim
            cx = x * cell + cell / 2
            cy = y * cell + cell / 2
            row.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" fill="{fill}"/>')
        if not row:
            continue
        if reveal:
            step = reveal_time / max(rows - 1, 1)
            delay = y * step
            out.append(
                f'<g class="{class_prefix}rw" style="animation-delay:{delay:.3f}s">'
                f'{"".join(row)}</g>'
            )
        else:
            out += row
    reveal_css = ""
    if reveal:
        reveal_css = (
            f'.{class_prefix}rw{{opacity:0;animation:{class_prefix}rv '
            f'{reveal_fade}s ease-out forwards}}'
            f'@keyframes {class_prefix}rv{{to{{opacity:1}}}}'
        )
    return "".join(out), cols * cell, rows * cell, reveal_css
