# filepath: /workspaces/dbx-container/src/dbx_container/images/dbfsfuse.py
from dbx_container.docker.builder import DockerInstruction
from dbx_container.docker.instructions import (
    EnvInstruction,
    RunInstruction,
)
from dbx_container.images.python import PythonDockerfile, PythonDockerfileVersions


class DbfsFuseDockerfile(PythonDockerfile):
    def __init__(
        self,
        base_image: str = "ubuntu:24.04",
        versions: PythonDockerfileVersions | None = None,
        instrs: list[DockerInstruction] | None = None,
    ) -> None:
        instructions = [
            RunInstruction(
                command=(
                    "apt-get update && apt-get install -y fuse && "
                    "apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*"
                )
            ),
            EnvInstruction(name="USER", value="root"),
        ]
        if instrs:
            instructions.extend(instrs)
        super().__init__(base_image=base_image, versions=versions, instrs=instructions)

    @property
    def image_name(self) -> str:
        return "dbfsfuse" + self.versions.python
