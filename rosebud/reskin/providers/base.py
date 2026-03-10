"""Base provider interface for reskin transforms."""


class ReskinProvider:
    """Abstract base class for reskin providers."""

    def transform(self, image_path: str, prompt: str, params: dict) -> bytes:
        """Transform a single image according to the given style prompt.

        Args:
            image_path: Absolute path to the source image.
            prompt: Fully constructed style prompt.
            params: Additional provider-specific parameters. Implementations
                may support ``reference_image_paths`` for extra style anchors.

        Returns:
            Reskinned image as bytes (PNG format).
        """
        raise NotImplementedError

    def transform_grid(self, grid_path: str, prompt: str,
                       output_path: str) -> bool:
        """Transform a grid image containing multiple sprites.

        This remains available for experimental grid workflows. Override this
        in providers that support grid mode.

        Args:
            grid_path: Path to the input grid PNG.
            prompt: Style prompt with per-cell descriptions.
            output_path: Where to write the restyled grid PNG.

        Returns:
            True on success, False on failure.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support grid mode. "
            f"Grid batching is not part of the normal sprite CLI workflow."
        )
