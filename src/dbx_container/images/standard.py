from dbx_container.docker.builder import DockerInstruction
from dbx_container.docker.instructions import (
    CommentInstruction,
    RunInstruction,
)
from dbx_container.images.dbfsfuse import DbfsFuseDockerfile, PythonDockerfileVersions


class StandardDockerfile(DbfsFuseDockerfile):
    """Standard Databricks container image that inherits from dbfsfuse and adds openssh-server functionality.

    Based on the official Databricks standard container.
    Reference: https://github.com/databricks/containers/blob/master/ubuntu/standard/Dockerfile
    """

    def __init__(
        self,
        base_image: str = "ubuntu:24.04",
        versions: PythonDockerfileVersions | None = None,
        instrs: list[DockerInstruction] | None = None,
    ) -> None:
        # Instructions specific to the standard image
        standard_instructions = [
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

        # Initialize the parent dbfsfuse dockerfile with our additional instructions
        super().__init__(base_image=base_image, versions=versions, instrs=standard_instructions)

    @property
    def image_name(self) -> str:
        return "standard" + self.versions.python
