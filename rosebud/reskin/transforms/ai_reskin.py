"""AI-powered reskinning via img2img providers."""

PROMPT_TEMPLATES = {
    "unit-sprite": (
        "Reskin this 2D pixel art game unit sprite. "
        "Preserve transparency, silhouette, and animation pose. "
        "Style: {style}"
    ),
    "building": (
        "Reskin this 2D pixel art game building sprite. "
        "Preserve transparency and structure. "
        "Style: {style}"
    ),
    "portrait": (
        "Reskin this character portrait. "
        "Preserve face composition and expression. "
        "Style: {style}"
    ),
}


def build_prompt(category: str, style_prompt: str) -> str:
    """Build a full prompt from asset category and theme style prompt."""
    template = PROMPT_TEMPLATES.get(category, PROMPT_TEMPLATES["unit-sprite"])
    return template.format(style=style_prompt)


def ai_reskin(
    image_path: str,
    category: str,
    style_prompt: str,
    provider,
    params: dict = None,
) -> bytes:
    """Reskin an image using an AI provider.

    Args:
        image_path: Path to source image.
        category: Asset category ("unit-sprite", "building", or "portrait").
        style_prompt: Theme style prompt.
        provider: Any object with a ``.transform()`` method
                  (e.g. a ReskinProvider instance).
        params: Optional provider-specific parameters.

    Returns:
        Reskinned image as bytes.
    """
    prompt = build_prompt(category, style_prompt)
    return provider.transform(image_path, prompt, params or {})
