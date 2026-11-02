"""Worst-case WCAG contrast per text run: the 5th-percentile background under its box."""

import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

RGB = tuple[int, int, int]


def channel(v: int) -> float:
    x = v / 255
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def lum(c: RGB) -> float:
    return 0.2126 * channel(c[0]) + 0.7152 * channel(c[1]) + 0.0722 * channel(c[2])


def ratio(a: float, b: float) -> float:
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def pixels(img: Image.Image, box: list[float]) -> list[RGB]:
    x, y, w, h = (int(round(v)) for v in box)
    xs = range(max(0, x), min(img.width, x + w), 2)
    ys = range(max(0, y), min(img.height, y + h), 2)
    return [img.getpixel((i, j)) for i in xs for j in ys]  # type: ignore[misc]


def worst(img: Image.Image, color: RGB, box: list[float]) -> float:
    rs = sorted(ratio(lum(color), lum(p)) for p in pixels(img, box))
    return rs[len(rs) // 20] if rs else 99.0


def needed(run: dict[str, Any]) -> float:
    large = run["size"] >= 24 or (run["size"] >= 18.66 and int(run["weight"]) >= 700)
    return 3.0 if large else 4.5


def rows(scene: dict[str, Any]) -> list[tuple[float, float, str, str, float]]:
    img = Image.open(scene["shot"]).convert("RGB")
    runs: list[dict[str, Any]] = scene["boxes"]
    return [
        (
            worst(img, tuple(r["color"]), r["box"]),
            needed(r),
            scene["scene"],
            r["text"],
            r["size"],
        )
        for r in runs
    ]


def main(path: str) -> None:
    scenes: list[dict[str, Any]] = json.loads(Path(path).read_text())
    found = [row for scene in scenes for row in rows(scene)]
    for r in sorted(found)[:12]:
        print(f"{r[0]:5.2f} need {r[1]}  {r[2]:7} {r[4]:>5}px  {r[3]}")
    print(f"{len(found)} runs, {sum(1 for r in found if r[0] < r[1])} below AA")


if __name__ == "__main__":
    main(sys.argv[1])
