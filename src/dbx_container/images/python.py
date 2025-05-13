# filepath: /workspaces/dbx-container/src/dbx_container/images/python.py
from dbx_container.docker.builder import DockerInstruction
from dbx_container.docker.instructions import (
    ArgInstruction,
    CommentInstruction,
    CopyInstruction,
    EnvInstruction,
    RunInstruction,
    UserInstruction,
)
from dbx_container.images.minimal import MinimalUbuntuDockerfileBuilder


class PythonDockerfileBuilder(MinimalUbuntuDockerfileBuilder):
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
            ArgInstruction(name="PYTHON_VERSION", default=f'"{python_version}"'),
            ArgInstruction(name="PIP_VERSION", default=f'"{pip_version}"'),
            ArgInstruction(name="SETUPTOOLS_VERSION", default=f'"{setuptools_version}"'),
            ArgInstruction(name="WHEEL_VERSION", default=f'"{wheel_version}"'),
            ArgInstruction(name="VIRTUALENV_VERSION", default=f'"{virtualenv_version}"'),
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
            CopyInstruction(src="src/dbx_container/data/requirements.txt", dest="/databricks/."),
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
        if instrs:
            instructions.extend(instrs)
        super().__init__(base_image=base_image, instrs=instructions)
