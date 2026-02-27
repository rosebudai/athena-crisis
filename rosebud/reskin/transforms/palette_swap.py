"""Algorithmic palette swap for icons and simple assets."""

import io
from typing import Dict, Tuple

from PIL import Image
import colorsys


# Color family hue ranges (in degrees, 0-360)
COLOR_FAMILIES = {
    "reds": ((-15, 15), (345, 360)),      # wraps around 0
    "browns": ((15, 45),),
    "greens": ((75, 165),),
    "silvers": None,                        # handled by saturation check
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)


def _classify_pixel_color(r: int, g: int, b: int) -> str:
    h, s, v = _rgb_to_hsv(r, g, b)
    hue_deg = h * 360

    # Desaturated bright pixels -> silvers
    if s < 0.15 and v > 0.5:
        return "silvers"
    # Very dark or desaturated pixels -> grays (tintable)
    if s < 0.1:
        if v > 0.08:
            return "grays"
        return "unknown"

    # Chromatic pixels -- classify by hue
    if hue_deg <= 15 or hue_deg >= 345:
        return "reds"
    if 15 < hue_deg <= 45:
        return "browns"
    if 45 < hue_deg <= 75:
        return "yellows"
    if 75 < hue_deg <= 165:
        return "greens"
    if 165 < hue_deg <= 195:
        return "cyans"
    if 195 < hue_deg <= 260:
        return "blues"
    if 260 < hue_deg <= 300:
        return "purples"
    if 300 < hue_deg < 345:
        return "magentas"

    return "unknown"


def palette_swap(image_path: str, palette: Dict[str, str]) -> bytes:
    """Swap color families in an image according to a palette mapping.

    Args:
        image_path: Path to source image.
        palette: Dict mapping color family names to target hex colors.

    Returns:
        Recolored image as PNG bytes.
    """
    img = Image.open(image_path).convert("RGBA")
    pixels = img.load()
    width, height = img.size

    # Precompute target HSV values
    targets = {}
    for family, hex_color in palette.items():
        tr, tg, tb = _hex_to_rgb(hex_color)
        targets[family] = _rgb_to_hsv(tr, tg, tb)

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue

            family = _classify_pixel_color(r, g, b)
            if family not in targets:
                continue

            # Preserve relative brightness, shift hue and saturation
            src_h, src_s, src_v = _rgb_to_hsv(r, g, b)
            tgt_h, tgt_s, tgt_v = targets[family]

            if family == "grays":
                # Tint grays: add target hue with gentle saturation
                new_v = src_v
                new_r, new_g, new_b = colorsys.hsv_to_rgb(
                    tgt_h, min(tgt_s, 0.4), new_v
                )
            else:
                # Chromatic: use target hue/sat, mix brightness
                new_v = (src_v * 0.6) + (tgt_v * 0.4)
                new_r, new_g, new_b = colorsys.hsv_to_rgb(
                    tgt_h, tgt_s, new_v
                )

            pixels[x, y] = (
                int(new_r * 255),
                int(new_g * 255),
                int(new_b * 255),
                a,
            )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
