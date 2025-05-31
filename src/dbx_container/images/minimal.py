from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction
from dbx_container.docker.instructions import (
    ArgInstruction,
    CommentInstruction,
    EnvInstruction,
    FromInstruction,
    RunInstruction,
    UserInstruction,
)


class MinimalUbuntuDockerfile(DockerfileBuilder):
    def __init__(self, base_image: str = "ubuntu:24.04", instrs: list[DockerInstruction] | None = None) -> None:
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
                command="curl -O https://cdn.azul.com/zulu/bin/zulu-repo_1.0.0-3_all.deb && apt-get install ./zulu-repo_1.0.0-3_all.deb && rm zulu-repo_1.0.0-3_all.deb"
            ),
            ArgInstruction(name="JDK8_VERSION", default='"8.0.432-1"'),
            ArgInstruction(name="JDK17_VERSION", default='"17.0.13-1"'),
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
        super().__init__(base_image=FromInstruction(base_image), instrs=instructions)

    @property
    def image_name(self) -> str:
        return "minimal"
