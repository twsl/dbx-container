# filepath: /workspaces/dbx-container/src/dbx_container/images/python.py
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dbx_container.docker.builder import DockerfileBuilder, DockerInstruction
from dbx_container.docker.instructions import (
    ArgInstruction,
    CommentInstruction,
    CopyInstruction,
    EnvInstruction,
    FromInstruction,
    LabelInstruction,
    RunInstruction,
)
from dbx_container.models.runtime import Runtime


# https://github.com/databricks/containers/blob/master/ubuntu/python/Dockerfile
@dataclass
class PythonDockerfileVersions:
    python: str = "3.12"
    pip: str = "25.0.1"
    setuptools: str = "74.0.0"
    wheel: str = "0.45.1"
    virtualenv: str = "20.29.3"


class PythonDockerfile(DockerfileBuilder):
    """Python container that builds on top of standard image.

    Can be built on top of GPU standard variant for GPU dependency chain.
    """

    def __init__(
        self,
        runtime: Runtime,
        base_image: str | None = None,
        versions: PythonDockerfileVersions | None = None,
        instrs: list[DockerInstruction] | None = None,
        registry: str | None = None,
        use_gpu_base: bool = False,
        requirements_path: str | None = None,
    ) -> None:
        self.use_gpu_base = use_gpu_base

        if versions is None:
            self.versions = PythonDockerfileVersions()
        else:
            self.versions = versions

        self.runtime = runtime
        # Determine base image
        if base_image is None:
            base_image = "dbx-runtime:standard-gpu" if use_gpu_base else "dbx-runtime:standard"

        # Determine requirements.txt path
        # If runtime is provided, use runtime-specific requirements.txt
        # Otherwise fall back to default static file
        if requirements_path is None:
            if runtime:
                # Use runtime-specific path that will be generated
                # This path is relative to the build context
                use_gpu_suffix = "-gpu" if use_gpu_base else ""
                sanitized_version = runtime.version.replace(" ", "-")
                ml_suffix = "-ml" if runtime.is_ml else ""
                requirements_path = f"data/python{use_gpu_suffix}/{sanitized_version}-ubuntu2404-py{self.versions.python.replace('.', '')}{ml_suffix}/requirements.txt"
            else:
                # Fall back to static requirements file
                requirements_path = "src/dbx_container/data/requirements.txt"

        instructions = [
            ArgInstruction(name="PYTHON_VERSION", default=f'"{self.versions.python}"'),
            ArgInstruction(name="PIP_VERSION", default=f'"{self.versions.pip}"'),
            ArgInstruction(name="SETUPTOOLS_VERSION", default=f'"{self.versions.setuptools}"'),
            ArgInstruction(name="WHEEL_VERSION", default=f'"{self.versions.wheel}"'),
            ArgInstruction(name="VIRTUALENV_VERSION", default=f'"{self.versions.virtualenv}"'),
            CommentInstruction(comment="Installs python and virtualenv for Spark and Notebooks"),
            RunInstruction(
                command=(
                    "apt-get update && apt-get install -y curl software-properties-common "
                    "python${PYTHON_VERSION} python${PYTHON_VERSION}-dev && "
                    "curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && "
                    "/usr/bin/python${PYTHON_VERSION} get-pip.py --break-system-packages pip==${PIP_VERSION} "
                    "setuptools==${SETUPTOOLS_VERSION} wheel==${WHEEL_VERSION} && "
                    "rm get-pip.py"
                )
            ),
            RunInstruction(
                command=(
                    "/usr/local/bin/pip${PYTHON_VERSION} install --break-system-packages --no-cache-dir "
                    "virtualenv==${VIRTUALENV_VERSION} && "
                    "sed -i -r 's/^(PERIODIC_UPDATE_ON_BY_DEFAULT) = True$/\\\\1 = False/' "
                    "/usr/local/lib/python${PYTHON_VERSION}/dist-packages/virtualenv/seed/embed/base_embed.py && "
                    "/usr/local/bin/pip${PYTHON_VERSION} download pip==${PIP_VERSION} --dest "
                    "/usr/local/lib/python${PYTHON_VERSION}/dist-packages/virtualenv_support/"
                )
            ),
            CommentInstruction(comment="Initialize the default environment that Spark and notebooks will use"),
            RunInstruction(
                command=(
                    "virtualenv --python=python${PYTHON_VERSION} --system-site-packages "
                    "/databricks/python3 --no-download --no-setuptools"
                )
            ),
            CommentInstruction(
                comment=(
                    "These python libraries are used by Databricks notebooks and the Python REPL. "
                    "You do not need to install pyspark - it is injected when the cluster is launched. "
                    "Versions are intended to reflect latest DBR LTS: "
                    "https://docs.databricks.com/en/release-notes/runtime/15.4lts.html#system-environment"
                )
            ),
            RunInstruction(command="apt-get install -y libpq-dev build-essential"),
            CopyInstruction(src=requirements_path, dest="/databricks/requirements.txt"),
            RunInstruction(command="/databricks/python3/bin/pip install --no-deps -r /databricks/requirements.txt"),
            CommentInstruction(comment="Specifies where Spark will look for the python process"),
            EnvInstruction(name="PYSPARK_PYTHON", value="/databricks/python3/bin/python3"),
            RunInstruction(
                command=(
                    "virtualenv --python=python${PYTHON_VERSION} --system-site-packages "
                    "/databricks/python-lsp --no-download --no-setuptools"
                )
            ),
            CopyInstruction(src="src/dbx_container/data/python-lsp-requirements.txt", dest="/databricks/."),
            RunInstruction(command="/databricks/python-lsp/bin/pip install -r /databricks/python-lsp-requirements.txt"),
        ]

        # Add runtime metadata labels if runtime is provided
        if runtime:
            # Sanitize runtime version for label (replace spaces with dashes)
            sanitized_version = runtime.version.replace(" ", "-")
            instructions.extend(
                [
                    CommentInstruction(comment="Runtime metadata"),
                    LabelInstruction(key="databricks.runtime.version", value=sanitized_version),
                    LabelInstruction(key="databricks.runtime.release_date", value=str(runtime.release_date)),
                    LabelInstruction(
                        key="databricks.runtime.end_of_support_date", value=str(runtime.end_of_support_date)
                    ),
                    LabelInstruction(key="databricks.runtime.spark_version", value=str(runtime.spark_version)),
                    LabelInstruction(key="databricks.runtime.url", value=str(runtime.url)),
                ]
            )

        if instrs:
            instructions.extend(instrs)
        super().__init__(base_image=FromInstruction(base_image), instrs=instructions, registry=registry)

    @property
    def base_name(self) -> str:
        """Return the base name without any variables."""
        return "python"

    @property
    def depends_on(self) -> str | None:
        """Return the base_name of the class this image depends on."""
        return "standard"

    @property
    def image_name(self) -> str:
        python_version = self.versions.python.replace(".", "")
        # Sanitize runtime version: replace spaces with dashes, keep dots
        runtime_version = self.runtime.version.replace(" ", "-")
        base = "python-gpu" if self.use_gpu_base else "python"
        return f"{base}-py{python_version}-{runtime_version}"
