from dbx_container.docker.builder import DockerInstruction
from dbx_container.docker.instructions import (
    CommentInstruction,
    EnvInstruction,
    RunInstruction,
)
from dbx_container.images.minimal import MinimalUbuntuDockerfile


class GpuDockerfile(MinimalUbuntuDockerfile):
    """GPU-enabled Databricks container image with CUDA 11.8 support.

    Note:
        Reference: https://github.com/databricks/containers/blob/master/ubuntu/gpu/cuda-11.8/base/Dockerfile
    """

    def __init__(
        self,
        cuda_version: str = "11.8.0",
        cudnn_version: str = "8",
        base_image: str = "ubuntu:22.04",  # TODO: Update to 24.04
        instrs: list[DockerInstruction] | None = None,
    ) -> None:
        self.cuda_version = cuda_version
        self.cudnn_version = cudnn_version
        base_image = f"nvidia/cuda:{cuda_version}-cudnn{cudnn_version}-runtime-{base_image.replace(':', '')}"
        # Instructions specific to the GPU image
        gpu_instructions = [
            CommentInstruction(comment="Disable NVIDIA repos to prevent accidental upgrades"),
            RunInstruction(
                command=(
                    "cd /etc/apt/sources.list.d && mv cuda-ubuntu2204-x86_64.list cuda-ubuntu2204-x86_64.list.disabled"
                )
            ),
            CommentInstruction(
                comment="Install R since command `R` is required for setting up driver on cluster creation"
            ),
            CommentInstruction(
                comment="See https://github.com/databricks/containers/blob/14042896b64285948300ed2d88a59eda87bb2a4d/ubuntu/R/Dockerfile#L16-L29"
            ),
            EnvInstruction(name="DEBIAN_FRONTEND", value="noninteractive"),
            RunInstruction(
                command=(
                    "apt-get update && "
                    "apt-get install --yes software-properties-common apt-transport-https && "
                    "gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9 && "
                    "gpg -a --export E298A3A825C0D65DFD57CBB651716619E084DAB9 | sudo apt-key add - && "
                    'add-apt-repository -y "deb [arch=amd64,i386] https://cran.rstudio.com/bin/linux/ubuntu $(lsb_release -cs)-cran40/" && '
                    "apt-get update && "
                    "apt-get install --yes libssl-dev r-base r-base-dev && "
                    'add-apt-repository -r "deb [arch=amd64,i386] https://cran.rstudio.com/bin/linux/ubuntu $(lsb_release -cs)-cran40/" && '
                    "apt-key del E298A3A825C0D65DFD57CBB651716619E084DAB9 && "
                    "apt-get clean && "
                    "rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*"
                )
            ),
            CommentInstruction(comment="Add new user for cluster library installation"),
            RunInstruction(command="useradd libraries && usermod -L libraries"),
        ]

        # Combine with any additional instructions passed in
        if instrs:
            gpu_instructions.extend(instrs)

        # Initialize the parent minimal dockerfile with our additional instructions
        super().__init__(base_image=base_image, instrs=gpu_instructions)

    @property
    def image_name(self) -> str:
        return "gpu" + self.cuda_version
