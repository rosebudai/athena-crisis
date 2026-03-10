"""AI-powered reskinning via img2img providers."""

from __future__ import annotations

from typing import Iterable, Optional


PROMPT_VERSION = "units-buildings-v2"

_COMMON_CONSTRAINTS = (
    "Keep the sprite sheet layout exact. Preserve exact canvas dimensions, "
    "frame count, frame order, spacing, registration, silhouette, and "
    "transparency. Preserve readable pixel-art structure. Do not add any "
    "background, labels, text, props, frames, blur, antialiasing, glow, or "
    "painterly rendering."
)

PROMPT_TEMPLATES = {
    "unit-sprite": (
        "Reskin this 2D pixel art game unit sprite sheet. "
        "Treat every frame as part of one coherent unit family. "
        "Preserve animation poses and directional readability. "
        "Style target: {style}. "
        f"{_COMMON_CONSTRAINTS}"
    ),
    "building": (
        "Reskin this 2D pixel art game building sprite sheet. "
        "Preserve building identity, material readability, and tile-aligned "
        "registration. "
        "Style target: {style}. "
        f"{_COMMON_CONSTRAINTS}"
    ),
    "portrait": (
        "Reskin this character portrait. "
        "Preserve composition, expression, and transparency where present. "
        "Style target: {style}. "
        f"{_COMMON_CONSTRAINTS}"
    ),
}


def build_prompt(
    category: str,
    style_prompt: str,
    asset_name: Optional[str] = None,
    reference_count: int = 0,
) -> str:
    """Build a full prompt from asset category and theme style prompt."""
    template = PROMPT_TEMPLATES.get(category, PROMPT_TEMPLATES["unit-sprite"])
    prompt = template.format(style=style_prompt)

    details = [prompt, f"Prompt version: {PROMPT_VERSION}."]
    if asset_name:
        details.append(f"Target asset name: {asset_name}.")
    if reference_count:
        details.append(
            "Additional reference image(s) are provided only for style guidance. "
            "Do not copy their composition or layout into the output sheet."
        )

    return " ".join(details)


def ai_reskin(
    image_path: str,
    category: str,
    style_prompt: str,
    provider,
    params: Optional[dict] = None,
    *,
    asset_name: Optional[str] = None,
    reference_image_paths: Optional[Iterable[str]] = None,
) -> bytes:
    """Reskin an image using an AI provider."""
    reference_image_paths = list(reference_image_paths or [])
    prompt = build_prompt(
        category,
        style_prompt,
        asset_name=asset_name,
        reference_count=len(reference_image_paths),
    )

    provider_params = dict(params or {})
    if reference_image_paths:
        provider_params["reference_image_paths"] = reference_image_paths

    return provider.transform(image_path, prompt, provider_params)
