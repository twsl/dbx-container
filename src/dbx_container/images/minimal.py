from typing import TYPE_CHECKING

from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction
from dbx_container.docker.instructions import (
    ArgInstruction,
    CommentInstruction,
    EnvInstruction,
    FromInstruction,
    RunInstruction,
)


class MinimalUbuntuDockerfile(DockerfileBuilder):
    """Minimal Ubuntu 24.04 LTS container with Java (JDK 8 and 17).

    Can be built on top of NVIDIA CUDA base image for GPU variant.
    """

    def __init__(
        self,
        base_image: str | None = None,
        instrs: list[DockerInstruction] | None = None,
        registry: str | None = None,
        use_gpu_base: bool = False,
        cuda_version: str = "12.8.1",
        ubuntu_version: str = "24.04",
        zulu_version: str = "1.0.0-3",
        jdk8_version: str = "8.0.432-1",
        jdk17_version: str = "17.0.16-1",
    ) -> None:
        self.use_gpu_base = use_gpu_base

        # Determine base image
        if base_image is None:
            base_image = "dbx-runtime:gpu" if use_gpu_base else f"ubuntu:{ubuntu_version}"

        instructions = [
            EnvInstruction(name="LANG", value="C.UTF-8"),
            EnvInstruction(name="LC_ALL", value="C.UTF-8"),
            CommentInstruction(
                comment="Workaround for https://bugs.launchpad.net/ubuntu/+source/ca-certificates/+bug/2066990"
            ),
            EnvInstruction(name="OPENSSL_FORCE_FIPS_MODE", value="0"),
            RunInstruction(
                command="apt-get update && apt-get -y upgrade && apt-get install --yes iproute2 bash sudo coreutils procps acl gnupg curl && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*"
            ),
            CommentInstruction(comment="Import Azul's public key"),
            RunInstruction(
                command="apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 0xB1998361219BD9C9"
            ),
            CommentInstruction(comment="Add the Azul package to the APT repository"),
            RunInstruction(
                command=f"curl -O https://cdn.azul.com/zulu/bin/zulu-repo_{zulu_version}_all.deb && apt-get install ./zulu-repo_{zulu_version}_all.deb && rm zulu-repo_{zulu_version}_all.deb"
            ),
            ArgInstruction(name="JDK8_VERSION", default=f'"{jdk8_version}"'),
            ArgInstruction(name="JDK17_VERSION", default=f'"{jdk17_version}"'),
            RunInstruction(command="apt-get update"),
            RunInstruction(
                command=(
                    "apt-get install -y zulu8=$JDK8_VERSION zulu8-jre=$JDK8_VERSION zulu8-jre-headless=$JDK8_VERSION zulu8-jdk=$JDK8_VERSION "
                    "zulu8-jdk-headless=$JDK8_VERSION zulu8-doc=$JDK8_VERSION zulu8-ca=$JDK8_VERSION zulu8-ca-jre=$JDK8_VERSION "
                    "zulu8-ca-jre-headless=$JDK8_VERSION zulu8-ca-jdk=$JDK8_VERSION zulu8-ca-jdk-headless=$JDK8_VERSION "
                    "zulu8-ca-doc=$JDK8_VERSION"
                )
            ),
            RunInstruction(
                command=(
                    "apt-get install -y zulu17=$JDK17_VERSION zulu17-jre=$JDK17_VERSION zulu17-jre-headless=$JDK17_VERSION zulu17-jdk=$JDK17_VERSION "
                    "zulu17-jdk-headless=$JDK17_VERSION zulu17-doc=$JDK17_VERSION zulu17-ca=$JDK17_VERSION zulu17-ca-jre=$JDK17_VERSION "
                    "zulu17-ca-jre-headless=$JDK17_VERSION zulu17-ca-jdk=$JDK17_VERSION zulu17-ca-jdk-headless=$JDK17_VERSION "
                    "zulu17-ca-doc=$JDK17_VERSION"
                )
            ),
            RunInstruction(command="update-java-alternatives -s zulu17-ca-amd64"),
            CommentInstruction(
                comment="This will install the cert store provided by ubuntu openjdk in case it's needed"
            ),
            CommentInstruction(comment="it's installed under /etc/ssl/certs/java/cacerts"),
            CommentInstruction(comment="Note that zulu comes with its own cert store, so this is by default not used."),
            CommentInstruction(
                comment="see https://support.azul.com/hc/en-us/articles/16981081133588-Using-https-TLS-SSL-certificates-provided-by-the-Operating-System"
            ),
            RunInstruction(command="apt-get install --yes ca-certificates-java"),
            CommentInstruction(comment="Add new user for cluster library installation"),
            RunInstruction(command="useradd libraries && usermod -L libraries"),
        ]

        if instrs:
            instructions.extend(instrs)
        super().__init__(base_image=FromInstruction(base_image), instrs=instructions, registry=registry)

    @property
    def base_name(self) -> str:
        """Return the base name without any variables."""
        return "minimal"

    @property
    def depends_on(self) -> str | None:
        """Return the base_name of the class this image depends on."""
        return "gpu" if self.use_gpu_base else None  # GPU variant depends on gpu image

    @property
    def image_name(self) -> str:
        return "minimal-gpu" if self.use_gpu_base else "minimal"
