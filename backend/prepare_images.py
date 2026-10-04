"""Give every product photo a white background (front-end improvement 2).

73 of the 102 provided photos have a pure-black backdrop, which hides navy and dark
garments, and some light photos have black bars down the sides. This flood-fills every
black area touching the image border (only near-black pixels
connected to the edge, so the garment and any black print inside it are untouched) and
writes white-backed copies to data/products_display/. The originals are never changed.

The photos are processed in parallel, one worker process per CPU core (Problem 9, backend
improvement 3): each photo is independent CPU work, so 102 photos take about as long as
the slowest few instead of all of them in a row.

Run once from the backend/ folder (main.py also runs it in the background on startup if
copies are missing):
    python prepare_images.py
"""

import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SOURCE_DIR = DATA_DIR / "products"
DISPLAY_DIR = DATA_DIR / "products_display"
from models import IMAGE_VERSION as VERSION  # bump it in models.py when the processing changes

BLACK_BORDER = 40  # border brightness below this counts as a black backdrop
FILL_TOLERANCE = 18  # how far from pure black a backdrop pixel may be (JPEG noise)
WHITE = (255, 255, 255)
MARKER = (255, 0, 255)  # temporary flood-fill color; magenta never appears in the catalogue


def has_black_backdrop(img: Image.Image) -> bool:
    a = np.asarray(img)
    border = np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3), a[:, :4].reshape(-1, 3), a[:, -4:].reshape(-1, 3)])
    return float(np.median(border)) < BLACK_BORDER


def whiten_backdrop(img: Image.Image) -> Image.Image:
    """Replace the black backdrop connected to the image edge with white."""
    out = img.copy()
    w, h = out.size
    # Seed the fill from points all around the border, so every edge-touching backdrop region is caught.
    step = max(1, min(w, h) // 40)
    seeds = [(x, y) for x in range(0, w, step) for y in (0, h - 1)] + [(x, y) for y in range(0, h, step) for x in (0, w - 1)]
    for xy in seeds:
        if max(out.getpixel(xy)) <= FILL_TOLERANCE:
            ImageDraw.floodfill(out, xy, MARKER, thresh=FILL_TOLERANCE)

    a = np.asarray(out).copy()
    backdrop = np.all(a == MARKER, axis=-1)
    a[backdrop] = WHITE

    # Soften the dark fringe that JPEG left around the garment edge: pixels right next to
    # the backdrop that are still almost black are blended toward white.
    near = np.asarray(Image.fromarray(backdrop.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0
    fringe = near & ~backdrop & (a.max(axis=-1) < 45)
    a[fringe] = (a[fringe] * 0.35 + np.array(WHITE) * 0.65).astype(np.uint8)
    return Image.fromarray(a)


def process_one(src: Path, force: bool = False) -> str:
    """Write one display copy. Runs in a worker process. Returns 'whitened', 'checked' or 'skipped'."""
    dest = DISPLAY_DIR / src.name
    if dest.exists() and not force:
        return "skipped"
    img = Image.open(src).convert("RGB")
    # Always fill: only near-black pixels connected to the border change, so photos that
    # already have a light backdrop are untouched apart from any black edge bars.
    whiten_backdrop(img).save(dest, quality=90)
    return "whitened" if has_black_backdrop(img) else "checked"


def prepare_all(force: bool = False, workers: int | None = None) -> tuple[int, int]:
    """Write a display copy of every product photo, in parallel. Returns (whitened, checked).

    workers=1 runs them one at a time (used to measure the speed-up).
    """
    DISPLAY_DIR.mkdir(exist_ok=True)
    sources = sorted(SOURCE_DIR.glob("*.jpg"))
    workers = workers or os.cpu_count() or 1
    if workers == 1:
        results = [process_one(src, force) for src in sources]
    else:
        # Each photo is independent CPU-bound work, so separate processes (not threads) run them truly at once.
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(process_one, sources, [force] * len(sources)))
    return results.count("whitened"), results.count("checked")


# ---------- Print artwork for the lookbook models (Problem 10) ----------
# The chest print of a real product, cut out as a transparent PNG, so it can be laid onto a
# model photo wearing a plain garment of the same color. Regions are rough fractions of the
# product photo (left, top, right, bottom); the exact print is found inside them.
PRINTS_DIR = DISPLAY_DIR / "prints"
PRINTS = {
    # product_id: (region, mode, threshold)
    #   mode "light": white ink on a dark garment (alpha from how much brighter than the fabric)
    #   mode "ink":   colored ink on heathered gray (alpha from color distance, high threshold
    #                 so the heather texture stays transparent)
    "basic-hoodie-big-yale": ((0.30, 0.42, 0.76, 0.57), "light", 60),
    "baseball-left-chest-crewneck": ((0.52, 0.18, 0.735, 0.31), "light", 60),
    "benjamin-franklin-1-4-zip": ((0.54, 0.20, 0.69, 0.335), "ink", 55),
    "super-heavyweight-crewneck-arched-yale-crest": ((0.335, 0.29, 0.58, 0.598), "ink", 60),
    "champion-reverse-weave-crewneck": ((0.27, 0.17, 0.68, 0.345), "ink", 60),
}


def extract_print(product_id: str, region: tuple[float, float, float, float], mode: str, threshold: float) -> Image.Image:
    """Cut the print out of a product photo, leaving the fabric transparent."""
    img = Image.open(SOURCE_DIR / f"{product_id}.jpg").convert("RGB")
    w, h = img.size
    box = (int(region[0] * w), int(region[1] * h), int(region[2] * w), int(region[3] * h))
    a = np.asarray(img.crop(box)).astype(float)
    # Fabric color = median of the region's border, which is plain garment.
    border = np.concatenate([a[:3].reshape(-1, 3), a[-3:].reshape(-1, 3), a[:, :3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)])
    base = np.median(border, axis=0)
    if mode == "light":
        diff = a.mean(axis=-1) - base.mean()  # only brighter-than-fabric pixels count
    else:
        diff = np.sqrt(((a - base) ** 2).sum(axis=-1))
    alpha = np.clip((diff - threshold) / 40, 0, 1)  # soft edge between fabric and ink
    if mode == "ink":
        # Drop scattered specks of heather texture: keep ink only where the area around it is mostly ink.
        density = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))) / 255
        alpha = alpha * (density > 0.18)
    ys, xs = np.where(alpha > 0.5)
    if len(xs) == 0:
        raise ValueError(f"No print found for {product_id}")
    pad = 3
    y0, y1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(a.shape[1], xs.max() + pad)
    rgb = a if mode != "light" else np.full_like(a, 245)  # white ink prints as clean off-white
    rgba = np.dstack([rgb, alpha * 255])[y0:y1, x0:x1].astype(np.uint8)
    return Image.fromarray(rgba, "RGBA").filter(ImageFilter.MedianFilter(3)) if mode == "ink" else Image.fromarray(rgba, "RGBA")


def prepare_prints(force: bool = False) -> int:
    PRINTS_DIR.mkdir(parents=True, exist_ok=True)
    made = 0
    for product_id, spec in PRINTS.items():
        dest = PRINTS_DIR / f"{product_id}.png"
        if dest.exists() and not force:
            continue
        extract_print(product_id, *spec).save(dest)
        made += 1
    return made


def ensure_display_images() -> None:
    """Called on server startup: build any missing display copies."""
    missing = {p.name for p in SOURCE_DIR.glob("*.jpg")} - {p.name for p in DISPLAY_DIR.glob("*.jpg")}
    if missing:
        prepare_all()
    prepare_prints()


if __name__ == "__main__":
    start = time.perf_counter()
    whitened, checked = prepare_all(force=True)
    prepare_prints(force=True)
    print(
        f"White backdrop added to {whitened} photos; {checked} light photos checked for black edges "
        f"({time.perf_counter() - start:.1f}s with {os.cpu_count()} workers). Saved in {DISPLAY_DIR}"
    )
