from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction
from dbx_container.docker.instructions import RunInstruction


class PipInstallInstruction(RunInstruction):
    """Installs Python dependencies via pip from a requirements file."""

    def __init__(self, requirements_file: str) -> None:
        super().__init__(f"pip install -r {requirements_file}")


class AptInstallInstruction(RunInstruction):
    """Installs packages via apt-get, with optional cache cleaning."""

    def __init__(self, packages: list[str], update: bool = True, clean: bool = True) -> None:
        command = "apt-get install -y " + " ".join(packages)
        if update:
            command = "apt-get update && " + command
        if clean:
            command += " && rm -rf /var/lib/apt/lists/*"
        super().__init__(command)
