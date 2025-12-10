from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction
from dbx_container.docker.instructions import (
    CommentInstruction,
    EnvInstruction,
    FromInstruction,
    RunInstruction,
)
from dbx_container.images.python import PythonDockerfileVersions


class GpuDockerfile(DockerfileBuilder):
    """GPU-enabled Databricks container image using official NVIDIA CUDA base image.

    Uses official NVIDIA CUDA images in the format: cuda_version-cudnn-runtime-ubuntu_version

    Note:
        Reference: https://github.com/databricks/containers/blob/master/ubuntu/gpu/cuda-11.8/base/Dockerfile
    """

    def __init__(
        self,
        cuda_version: str = "12.8.1",  # make compatible with default Linux CUDA version https://pytorch.org/get-started/locally/
        ubuntu_version: str = "24.04",
        versions: PythonDockerfileVersions | None = None,
        instrs: list[DockerInstruction] | None = None,
        registry: str | None = None,
    ) -> None:
        self.cuda_version = cuda_version
        self.ubuntu_version = ubuntu_version
        self.versions = versions or PythonDockerfileVersions()

        # Construct the official NVIDIA CUDA base image name
        # Format: cuda_version-cudnn-runtime-ubuntu_version
        # Example: 12.8.1-cudnn-runtime-ubuntu24.04
        ubuntu_tag = ubuntu_version.replace(".", "")
        base_image_name = f"nvidia/cuda:{cuda_version}-cudnn-runtime-ubuntu{ubuntu_tag}"

        # Instructions specific to the GPU image
        gpu_instructions = [
            CommentInstruction(comment="Using official NVIDIA CUDA base image"),
            CommentInstruction(comment=f"CUDA {cuda_version}, Ubuntu {ubuntu_version}"),
            EnvInstruction(name="NVIDIA_VISIBLE_DEVICES", value="all"),
            EnvInstruction(name="NVIDIA_DRIVER_CAPABILITIES", value="compute,utility"),
            CommentInstruction(
                comment="Install R since command `R` is required for setting up driver on cluster creation"
            ),
            CommentInstruction(
                comment="See https://github.com/databricks/containers/blob/5cb1057f74dce823d4997b727087d0317deb325d/ubuntu/R/Dockerfile#L16-L31"
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
        ]

        # Combine with any additional instructions passed in
        if instrs:
            gpu_instructions.extend(instrs)

        super().__init__(base_image=FromInstruction(base_image_name), instrs=gpu_instructions, registry=registry)

    @property
    def base_name(self) -> str:
        """Return the base name without any variables."""
        return "gpu"

    @property
    def depends_on(self) -> str | None:
        """Return the base_name of the class this image depends on."""
        return None  # GPU uses official NVIDIA base image, not our internal images

    @property
    def image_name(self) -> str:
        return "gpu"
