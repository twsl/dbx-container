from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction
from dbx_container.docker.instructions import (
    CommentInstruction,
    EnvInstruction,
    FromInstruction,
    RunInstruction,
)
from dbx_container.images.python import PythonDockerfileVersions


class StandardDockerfile(DockerfileBuilder):
    """Standard container that builds on top of minimal image and adds FUSE and SSH server.

    Can be built on top of GPU minimal variant for GPU dependency chain.
    """

    def __init__(
        self,
        base_image: str | None = None,
        versions: PythonDockerfileVersions | None = None,
        instrs: list[DockerInstruction] | None = None,
        registry: str | None = None,
        use_gpu_base: bool = False,
        ubuntu_version: str = "24.04",
    ) -> None:
        self.use_gpu_base = use_gpu_base
        self.versions = versions or PythonDockerfileVersions()
        self.ubuntu_version = ubuntu_version

        # Determine base image
        if base_image is None:
            base_image = "dbx-runtime:minimal-gpu" if use_gpu_base else "dbx-runtime:minimal"

        # Instructions specific to the standard image
        standard_instructions = [
            CommentInstruction(comment="Install FUSE for DBFS capabilities"),
            RunInstruction(
                command=(
                    "apt-get update && apt-get install -y fuse && "
                    "apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*"
                )
            ),
            EnvInstruction(name="USER", value="root"),
            CommentInstruction(comment="Install openssh-server for remote access capabilities"),
            RunInstruction(
                command=(
                    "apt-get update && "
                    "apt-get install -y openssh-server && "
                    "apt-get clean && "
                    "rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*"
                )
            ),
            CommentInstruction(
                comment="Warning: you still need to start the ssh process with `sudo service ssh start`"
            ),
        ]

        # Combine with any additional instructions passed in
        if instrs:
            standard_instructions.extend(instrs)

        super().__init__(base_image=FromInstruction(base_image), instrs=standard_instructions, registry=registry)

    @property
    def base_name(self) -> str:
        """Return the base name without any variables."""
        return "standard"

    @property
    def depends_on(self) -> str | None:
        """Return the base_name of the class this image depends on."""
        return "minimal"

    @property
    def image_name(self) -> str:
        base = "standard-gpu" if self.use_gpu_base else "standard"
        return base
