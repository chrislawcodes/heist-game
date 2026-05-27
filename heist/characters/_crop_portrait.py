"""Crop a thin border off a portrait image.

Usage:
    python -m heist.characters._crop_portrait c09_pearl.jpg
    python -m heist.characters._crop_portrait c09_pearl.jpg --px 12
    python -m heist.characters._crop_portrait c09_pearl.jpg --px 12 --preview

Options:
    --px N      Pixels to remove from each edge (default: 10)
    --preview   Show the result in your default image viewer without saving
    --out PATH  Save to a different path (default: overwrites in-place)

The script crops equal amounts from all four sides. If the border is thicker
on some sides, run twice with different --px values (or open in Preview and
crop manually — sometimes that's faster).

Requires: Pillow  →  pip install Pillow
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def crop(src: Path, px: int, out: Path | None, preview: bool,
         auto: bool = False, threshold: int = 12) -> None:
    try:
        from PIL import Image, ImageChops
    except ImportError:
        print("ERROR: Pillow is not installed.  Run:  pip install Pillow")
        sys.exit(1)

    img = Image.open(src)
    w, h = img.size
    if auto:
        # Detect the white frame: bounding box of everything that differs from
        # pure white by more than `threshold`. Trims exactly the border, however
        # thick (or none), instead of a guessed fixed amount.
        rgb = img.convert("RGB")
        diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (255, 255, 255)))
        bbox = diff.convert("L").point(lambda v: 255 if v > threshold else 0).getbbox()
        if not bbox or bbox == (0, 0, w, h):
            print(f"  {src.name}: no white border detected — left as-is.")
            if not preview and out and out != src:
                img.save(out, quality=95)
            return
        cropped = img.crop(bbox)
    else:
        if px * 2 >= w or px * 2 >= h:
            print(f"ERROR: --px {px} is too large for a {w}x{h} image.")
            sys.exit(1)
        cropped = img.crop((px, px, w - px, h - px))

    if preview:
        cropped.show()
        print(f"Preview shown ({w}x{h} → {cropped.size[0]}x{cropped.size[1]}, {px}px removed per edge).")
        return

    dest = out or src
    cropped.save(dest, quality=95)
    print(f"Saved {dest}  ({w}x{h} → {cropped.size[0]}x{cropped.size[1]}, {px}px removed per edge).")


def main() -> None:
    here = Path(__file__).parent

    parser = argparse.ArgumentParser(description="Crop a border off a portrait JPEG.")
    parser.add_argument("image", help="Filename (e.g. c09_pearl.jpg) or full path")
    parser.add_argument("--px", type=int, default=10, help="Pixels to remove from each edge (default 10)")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-detect and trim the white border (ignores --px)")
    parser.add_argument("--threshold", type=int, default=12,
                        help="With --auto: how far from pure white still counts as border (default 12)")
    parser.add_argument("--preview", action="store_true", help="Show result without saving")
    parser.add_argument("--out", help="Output path (default: overwrite in-place)")
    args = parser.parse_args()

    src = Path(args.image)
    if not src.is_absolute():
        src = here / src
    # If the given name doesn't exist, try the other jpeg/jpg extension
    if not src.exists():
        alt_ext = ".jpg" if src.suffix.lower() == ".jpeg" else ".jpeg"
        alt = src.with_suffix(alt_ext)
        if alt.exists():
            src = alt
        else:
            print(f"ERROR: file not found: {src} (also tried {alt.name})")
            sys.exit(1)

    out = Path(args.out) if args.out else None
    crop(src, args.px, out, args.preview, auto=args.auto, threshold=args.threshold)


if __name__ == "__main__":
    main()
