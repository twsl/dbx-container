from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction

# https://docs.docker.com/reference/dockerfile/


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


class CommentInstruction(DockerInstruction):
    """Adds a comment to the Dockerfile."""

    def __init__(self, comment: str) -> None:
        self.comment = comment

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"# {self.comment}")


class LabelInstruction(DockerInstruction):
    """Adds a LABEL instruction."""

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"LABEL {self.key}={self.value}")


class ExposeInstruction(DockerInstruction):
    """Adds an EXPOSE instruction."""

    def __init__(self, port: int) -> None:
        self.port = port

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"EXPOSE {self.port}")


class UserInstruction(DockerInstruction):
    """Adds a USER instruction."""

    def __init__(self, user: str) -> None:
        self.user = user

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"USER {self.user}")


class VolumeInstruction(DockerInstruction):
    """Adds a VOLUME instruction."""

    def __init__(self, path: str) -> None:
        self.path = path

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"VOLUME {self.path}")


class HealthcheckInstruction(DockerInstruction):
    """Adds a HEALTHCHECK instruction."""

    def __init__(self, command: str, interval: str = "30s", timeout: str = "30s", retries: int = 3) -> None:
        self.command = command
        self.interval = interval
        self.timeout = timeout
        self.retries = retries

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(
            f"HEALTHCHECK --interval={self.interval} --timeout={self.timeout} --retries={self.retries} CMD {self.command}"
        )


class ShellInstruction(DockerInstruction):
    """Adds a SHELL instruction."""

    def __init__(self, shell: str) -> None:
        self.shell = shell

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"SHELL {self.shell}")


class AddInstruction(DockerInstruction):
    """Adds an ADD instruction."""

    def __init__(self, src: str, dest: str) -> None:
        self.src = src
        self.dest = dest

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"ADD {self.src} {self.dest}")


class StopSignalInstruction(DockerInstruction):
    """Adds a STOP instruction."""

    def __init__(self, signal: str) -> None:
        self.signal = signal

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"STOPSIGNAL {self.signal}")


class OnbuildInstruction(DockerInstruction):
    """Adds an ONBUILD instruction."""

    def __init__(self, instruction: str) -> None:
        self.instruction = instruction

    def apply(self, builder: DockerfileBuilder) -> None:
        builder.add_instruction(f"ONBUILD {self.instruction}")
