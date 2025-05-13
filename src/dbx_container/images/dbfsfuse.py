# filepath: /workspaces/dbx-container/src/dbx_container/images/dbfsfuse.py
from dbx_container.docker.builder import DockerInstruction
from dbx_container.docker.instructions import (
    EnvInstruction,
    RunInstruction,
)
from dbx_container.images.python import PythonDockerfileBuilder


class DbfsFuseDockerfileBuilder(PythonDockerfileBuilder):
    def __init__(
        self,
        base_image: str = "ubuntu:24.04",
        python_version: str = "3.12",
        pip_version: str = "24.0",
        setuptools_version: str = "74.0.0",
        wheel_version: str = "0.38.4",
        virtualenv_version: str = "20.26.2",
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
        super().__init__(base_image=base_image, instrs=instructions)
