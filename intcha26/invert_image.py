#!/usr/bin/env python3
"""Luminance-invert an image to produce a dark-mode version.

Preserves hue and saturation — only the L channel is inverted and remapped
so that originally-white pixels land on a configurable target background
color (default #191919, matching the reveal.js dark theme).

Usage:
    python invert_image.py INPUT [OUTPUT] [--bg #RRGGBB] [--sat 1.08]

Examples:
    python invert_image.py images/fig.png
    python invert_image.py images/fig.png images/fig_dark.png --bg #222222
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def hex_to_lightness(h: str) -> float:
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    return (max(r, g, b) + min(r, g, b)) / 2


def invert(src: Path, dst: Path, bg_hex: str = '#191919', sat_boost: float = 1.08):
    bg_l = hex_to_lightness(bg_hex)

    img = Image.open(src).convert('RGB')
    arr = np.asarray(img).astype(np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

    mx = arr.max(axis=-1)
    mn = arr.min(axis=-1)
    l = (mx + mn) / 2.0
    d = mx - mn

    denom = np.maximum(1 - np.abs(2 * l - 1), 1e-6)
    s = np.where(d == 0, 0, d / denom)

    dsafe = np.where(d == 0, 1, d)
    rc = (mx - r) / dsafe
    gc = (mx - g) / dsafe
    bc = (mx - b) / dsafe
    h = np.where(r == mx, bc - gc,
         np.where(g == mx, 2.0 + rc - bc, 4.0 + gc - rc))
    h = (h / 6.0) % 1.0
    h = np.where(d == 0, 0, h)

    # Invert lightness; compress so white -> bg_l, black -> 1.0
    l_new = bg_l + (1.0 - l) * (1.0 - bg_l)
    s_new = np.clip(s * sat_boost, 0, 1)

    def hue_to_rgb(p, q, t):
        t = t % 1.0
        return np.where(t < 1/6, p + (q - p) * 6 * t,
               np.where(t < 1/2, q,
               np.where(t < 2/3, p + (q - p) * (2/3 - t) * 6, p)))

    q = np.where(l_new < 0.5, l_new * (1 + s_new), l_new + s_new - l_new * s_new)
    p = 2 * l_new - q
    r2 = hue_to_rgb(p, q, h + 1/3)
    g2 = hue_to_rgb(p, q, h)
    b2 = hue_to_rgb(p, q, h - 1/3)

    # Near-gray pixels: use the inverted lightness directly (cleaner)
    gray = s < 0.05
    r2 = np.where(gray, l_new, r2)
    g2 = np.where(gray, l_new, g2)
    b2 = np.where(gray, l_new, b2)

    out = np.clip(np.stack([r2, g2, b2], -1) * 255, 0, 255).astype(np.uint8)
    Image.fromarray(out).save(dst, 'PNG', optimize=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('input', type=Path, help='source image')
    ap.add_argument('output', type=Path, nargs='?',
                    help='destination (default: <stem>_dark.png next to input)')
    ap.add_argument('--bg', default='#191919',
                    help='target background color for originally-white pixels (default: #191919)')
    ap.add_argument('--sat', type=float, default=1.08,
                    help='saturation multiplier (default: 1.08)')
    args = ap.parse_args()

    src = args.input
    if not src.exists():
        sys.exit(f'input not found: {src}')

    dst = args.output
    if dst is None:
        stem = src.name.split('.')[0]  # strip all extensions (handles .png.webp)
        dst = src.parent / f'{stem}_dark.png'

    invert(src, dst, bg_hex=args.bg, sat_boost=args.sat)
    print(f'wrote {dst}')


if __name__ == '__main__':
    main()
