from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction

# https://docs.docker.com/reference/dockerfile/


class FromInstruction(DockerInstruction):
    """Adds a FROM instruction."""

    def __init__(self, image: str) -> None:
        self.image = image

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"FROM {self.image}"


class ArgInstruction(DockerInstruction):
    """Adds an ARG instruction."""

    def __init__(self, name: str, default: str | None = None) -> None:
        self.name = name
        self.default = default

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        if self.default is None:
            return f"ARG {self.name}"
        return f"ARG {self.name}={self.default}"


class EnvInstruction(DockerInstruction):
    """Adds an ENV instruction."""

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"ENV {self.name}={self.value}"


class RunInstruction(DockerInstruction):
    """Adds a RUN instruction."""

    def __init__(self, command: str) -> None:
        self.command = command

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"RUN {self.command}"


class WorkdirInstruction(DockerInstruction):
    """Adds a WORKDIR instruction."""

    def __init__(self, path: str) -> None:
        self.path = path

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"WORKDIR {self.path}"


class EntrypointInstruction(DockerInstruction):
    """Adds an ENTRYPOINT instruction."""

    def __init__(self, entrypoint: str) -> None:
        self.entrypoint = entrypoint

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"ENTRYPOINT {self.entrypoint}"


class CopyInstruction(DockerInstruction):
    """Copies files or directories into the image, optionally with --chown."""

    def __init__(self, src: str, dest: str, chown: str | None = None) -> None:
        self.src = src
        self.dest = dest
        self.chown = chown

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        if self.chown:
            return f"COPY --chown={self.chown} {self.src} {self.dest}"
        return f"COPY {self.src} {self.dest}"


class CmdInstruction(DockerInstruction):
    """Adds a CMD instruction."""

    def __init__(self, cmd: str) -> None:
        self.cmd = cmd

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"CMD {self.cmd}"


class CommentInstruction(DockerInstruction):
    """Adds a comment to the Dockerfile."""

    def __init__(self, comment: str) -> None:
        self.comment = comment

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"# {self.comment}"


class LabelInstruction(DockerInstruction):
    """Adds a LABEL instruction."""

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"LABEL {self.key}={self.value}"


class ExposeInstruction(DockerInstruction):
    """Adds an EXPOSE instruction."""

    def __init__(self, port: int) -> None:
        self.port = port

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"EXPOSE {self.port}"


class UserInstruction(DockerInstruction):
    """Adds a USER instruction."""

    def __init__(self, user: str) -> None:
        self.user = user

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"USER {self.user}"


class VolumeInstruction(DockerInstruction):
    """Adds a VOLUME instruction."""

    def __init__(self, path: str) -> None:
        self.path = path

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"VOLUME {self.path}"


class HealthcheckInstruction(DockerInstruction):
    """Adds a HEALTHCHECK instruction."""

    def __init__(self, command: str, interval: str = "30s", timeout: str = "30s", retries: int = 3) -> None:
        self.command = command
        self.interval = interval
        self.timeout = timeout
        self.retries = retries

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"HEALTHCHECK --interval={self.interval} --timeout={self.timeout} --retries={self.retries} CMD {self.command}"


class ShellInstruction(DockerInstruction):
    """Adds a SHELL instruction."""

    def __init__(self, shell: str) -> None:
        self.shell = shell

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"SHELL {self.shell}"


class AddInstruction(DockerInstruction):
    """Adds an ADD instruction."""

    def __init__(self, src: str, dest: str) -> None:
        self.src = src
        self.dest = dest

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"ADD {self.src} {self.dest}"


class StopSignalInstruction(DockerInstruction):
    """Adds a STOP instruction."""

    def __init__(self, signal: str) -> None:
        self.signal = signal

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"STOPSIGNAL {self.signal}"


class OnbuildInstruction(DockerInstruction):
    """Adds an ONBUILD instruction."""

    def __init__(self, instruction: str) -> None:
        self.instruction = instruction

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(str(self))

    def __str__(self) -> str:
        return f"ONBUILD {self.instruction}"
