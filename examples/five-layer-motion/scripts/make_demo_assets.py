#!/usr/bin/env python3
"""Derive a small, local demo asset set from the approved hero frame."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    image = Image.open(args.input).convert("RGB")
    rgb = np.asarray(image).astype(np.int16)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    height, width = rgb.shape[:2]

    # The hero frame has one large blue paper disk. A geometry mask is more
    # faithful than a color mask here because the disk contains dark halftone
    # ink that would otherwise leak through the clean plate.
    blue_image_mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(blue_image_mask).ellipse((880, 85, 1405, 550), fill=255)
    blue = np.asarray(blue_image_mask) > 0

    # Keep the dark arrow as a reference layer too. It is not moved in this
    # smoke test, but the original-frame extraction is preserved for future
    # iterations and manifest traceability.
    navy = (r < 90) & (g < 115) & (b < 165) & (b >= r)
    navy_roi = np.zeros_like(navy)
    navy_roi[430:height, :min(width, 1060)] = True
    navy = navy & navy_roi

    def rgba_layer(mask: np.ndarray, feather: float = 0.7) -> Image.Image:
        alpha = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
        # A very small feather keeps the original printed edge without making
        # the cutout look digitally clipped at video resolution.
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=feather))
        layer = image.convert("RGBA")
        layer.putalpha(alpha)
        return layer

    def save_cropped(mask: np.ndarray, name: str, feather: float = 0.7) -> tuple[int, int, int, int]:
        alpha = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
        bbox = alpha.getbbox()
        if bbox is None:
            raise RuntimeError(f"empty mask for {name}")
        rgba_layer(mask, feather=feather).crop(bbox).save(args.output_dir / name)
        return bbox

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rgba_layer(blue).save(args.output_dir / "scene-01-blue-circle.png")
    rgba_layer(blue).crop((880, 85, 1406, 551)).save(args.output_dir / "scene-01-blue-circle-crop.png")
    rgba_layer(navy).save(args.output_dir / "scene-01-arrow-reference.png")

    # Separate the other visually heavy paper pieces. These are original-frame
    # derivatives, not regenerated illustrations. Moving several independent
    # layers creates real occlusion and recomposition instead of a Ken Burns
    # treatment on a mostly flat image.
    red = (r > 145) & (r > g * 1.35) & (r > b * 1.25) & (g < 155)
    red_roi = np.zeros_like(red)
    red_roi[470:760, 350:1540] = True
    red = red & red_roi

    def polygon_mask(points: list[tuple[int, int]]) -> np.ndarray:
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).polygon(points, fill=255)
        return np.asarray(mask) > 0

    top_sheet = polygon_mask([(680, 118), (1435, 48), (1568, 590), (704, 560)])
    top_sheet = top_sheet & ~blue & ~navy

    bottom_sheet = polygon_mask([(495, 545), (1518, 566), (1510, 780), (335, 912)])
    bottom_sheet = bottom_sheet & ~red & ~navy

    arrow_bbox = save_cropped(navy, "scene-01-arrow-crop.png", feather=0.55)
    red_bbox = save_cropped(red, "scene-01-red-strip-crop.png", feather=0.55)
    top_bbox = save_cropped(top_sheet, "scene-01-top-sheet-crop.png", feather=0.45)
    bottom_bbox = save_cropped(bottom_sheet, "scene-01-bottom-sheet-crop.png", feather=0.45)

    # Local clean plate: clone nearby unoccupied paper from the same sheet,
    # then blend it only through the extracted circle mask. No new provider
    # call is made and the approved frame remains the visual source of truth.
    clean = image.copy()
    patch = image.crop((690, 130, 850, 370)).resize((600, 560), Image.Resampling.BICUBIC)
    patch = patch.filter(ImageFilter.GaussianBlur(radius=0.35))
    patch_rgba = patch.convert("RGBA")
    patch_mask = blue_image_mask
    clean_rgba = clean.convert("RGBA")
    clean_rgba.paste(patch_rgba, (820, 55), patch_mask.crop((820, 55, 1420, 615)))
    clean_rgba.save(args.output_dir / "scene-01-cleanplate.png")

    # Build a neutral paper stage from one large unoccupied area of the
    # approved frame. A single continuous enlargement avoids visible tiling
    # symmetry while retaining the source's real fibre and print character.
    texture = image.crop((115, 78, 690, 485))
    stage = texture.resize((width, height), Image.Resampling.LANCZOS)
    stage = ImageEnhance.Contrast(stage).enhance(0.94)
    stage = ImageEnhance.Sharpness(stage).enhance(1.18)
    stage.save(args.output_dir / "scene-01-paper-stage.png")

    # A second clean plate keeps the full approved still available as an
    # explicit background record for audit and comparison.
    image.save(args.output_dir / "scene-01-hero-copy.png")
    print(
        "derived bboxes",
        {
            "bottom": bottom_bbox,
            "red": red_bbox,
            "top": top_bbox,
            "arrow": arrow_bbox,
            "circle": (880, 85, 1406, 551),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
