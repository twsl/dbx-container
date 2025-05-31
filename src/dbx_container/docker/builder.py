from abc import ABC, abstractmethod, update_abstractmethods

from dbx_container.utils.stringbuilder import StringBuilder


class DockerInstruction(ABC):
    """A composable Dockerfile step."""

    @abstractmethod
    def apply(self, builder: "DockerfileBuilder") -> None:
        """Apply this instruction to the DockerfileBuilder."""
        pass


class DockerfileBuilder:
    """Builds a Dockerfile from a base image and an optional list of features."""

    # Default namespace for Docker images
    DEFAULT_NAMESPACE = "ghcr.io/twsl"

    def __init__(self, base_image: DockerInstruction, instrs: list[DockerInstruction] | None = None) -> None:
        self.builder = StringBuilder()
        self.base_image = base_image
        self.base_image.apply(self)
        # Apply any initial features
        if instrs:
            for instr in instrs:
                instr.apply(self)

    @property
    def image_name(self) -> str:
        return getattr(self.base_image, "image", str(self.base_image))

    @property
    def full_image_name(self) -> str:
        """Get the full image name with namespace."""
        return f"{self.DEFAULT_NAMESPACE}/{self.image_name}"

    def add_instruction(self, instruction: str) -> "DockerfileBuilder":
        """Add a generic instruction to the Dockerfile."""
        self.builder.append_line(instruction)
        return self

    def add(self, feature: DockerInstruction) -> "DockerfileBuilder":
        """Compose a feature into this Dockerfile."""
        feature.apply(self)
        return self

    def __add__(self, instruction: DockerInstruction) -> "DockerfileBuilder":
        """Allow `builder + instruction` to apply a feature."""
        instruction.apply(self)
        return self

    @classmethod
    def from_features(cls, base_image: DockerInstruction, *features: DockerInstruction) -> "DockerfileBuilder":
        """Construct a builder with base image and a sequence of features."""
        return cls(base_image, list(features))

    def __call__(self, *features: DockerInstruction) -> "DockerfileBuilder":
        """Apply multiple features in a single call, returning self for chaining.

        Example:
            builder = DockerfileBuilder("python:3.11-slim")(ArgFeature(...), EnvFeature(...))
        """
        for feat in features:
            feat.apply(self)
        return self

    def render(self) -> str:
        """Render the complete Dockerfile as a string."""
        return str(self.builder)
