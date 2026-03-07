"""
Optimize landing page photos for web: resize to display size (2x for retina),
compress JPEG. Run from project root: python scripts/optimize_landing_photos.py

Photos are shown at 200x200px in CSS; we output 400x400 for sharp retina display.
"""
import os
import sys

# Project root = parent of scripts/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS_DIR = os.path.join(ROOT, "static", "landing-photos")
SIZE = 400  # 2x of 200px display
JPEG_QUALITY = 82


def main():
    try:
        from PIL import Image
    except ImportError:
        print("Install Pillow: pip install Pillow", file=sys.stderr)
        sys.exit(1)

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    total_before = 0
    total_after = 0

    for name in sorted(os.listdir(PHOTOS_DIR)):
        if not name.lower().endswith((".jpg", ".jpeg")):
            continue
        path = os.path.join(PHOTOS_DIR, name)
        if not os.path.isfile(path):
            continue

        size_before = os.path.getsize(path)
        total_before += size_before

        img = Image.open(path).convert("RGB")
        w, h = img.size
        # Center-crop to square then resize
        if w != h:
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
        img = img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)

        img.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
        size_after = os.path.getsize(path)
        total_after += size_after
        print(f"{name}: {size_before / 1024:.1f} KB -> {size_after / 1024:.1f} KB")

    if total_before:
        print(f"Total: {total_before / 1024 / 1024:.2f} MB -> {total_after / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
