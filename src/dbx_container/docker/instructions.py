from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction


class FromInstruction(DockerInstruction):
    """Adds a FROM instruction."""

    def __init__(self, image: str) -> None:
        self.image = image

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"FROM {self.image}")


class ArgInstruction(DockerInstruction):
    """Adds an ARG instruction."""

    def __init__(self, name: str, default: str | None = None) -> None:
        self.name = name
        self.default = default

    def apply(self, builder: DockerfileBuilder) -> None:
        if self.default is None:
            builder.add_instruction(f"ARG {self.name}")
        else:
            builder.add_instruction(f"ARG {self.name}={self.default}")


class EnvInstruction(DockerInstruction):
    """Adds an ENV instruction."""

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"ENV {self.name}={self.value}")


class RunInstruction(DockerInstruction):
    """Adds a RUN instruction."""

    def __init__(self, command: str) -> None:
        self.command = command

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"RUN {self.command}")


class WorkdirInstruction(DockerInstruction):
    """Adds a WORKDIR instruction."""

    def __init__(self, path: str) -> None:
        self.path = path

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"WORKDIR {self.path}")


class EntrypointInstruction(DockerInstruction):
    """Adds an ENTRYPOINT instruction."""

    def __init__(self, entrypoint: str) -> None:
        self.entrypoint = entrypoint

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"ENTRYPOINT {self.entrypoint}")


class CopyInstruction(DockerInstruction):
    """Copies files or directories into the image, optionally with --chown."""

    def __init__(self, src: str, dest: str, chown: str | None = None) -> None:
        self.src = src
        self.dest = dest
        self.chown = chown

    def apply(self, builder: DockerfileBuilder) -> None:
        prefix = f"--chown={self.chown} " if self.chown else ""
        builder.add_instruction(f"COPY {prefix}{self.src} {self.dest}")


class CmdInstruction(DockerInstruction):
    """Adds a CMD instruction."""

    def __init__(self, cmd: str) -> None:
        self.cmd = cmd

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"CMD {self.cmd}")
