import json
from pathlib import Path
from typing import Any

from dbx_container.data.scraper import RuntimeScraper
from dbx_container.images.dbfsfuse import DbfsFuseDockerfile
from dbx_container.images.gpu import GpuDockerfile
from dbx_container.images.minimal import MinimalUbuntuDockerfile
from dbx_container.images.python import PythonDockerfile, PythonDockerfileVersions
from dbx_container.images.standard import StandardDockerfile
from dbx_container.models.runtime import Runtime
from dbx_container.utils.logging import get_logger


class RuntimeContainerEngine:
    """Engine for building container variations across all Databricks runtimes."""

    def __init__(
        self,
        data_dir: Path = Path("data"),
        max_workers: int = 5,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the ContainerEngine.

        Args:
            data_dir: Directory where to save generated files
            max_workers: Maximum number of worker threads for scraping
            verify_ssl: Whether to verify SSL certificates when making HTTP requests
        """
        self.logger = get_logger(self.__class__.__name__)
        self.data_dir = Path(data_dir)
        self.scraper = RuntimeScraper(
            max_workers=max_workers,
            verify_ssl=verify_ssl,
            enable_save_load=True,
            data_dir=data_dir,
        )

        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)

        # Image type configurations
        self.image_types = {
            "minimal": {
                "class": MinimalUbuntuDockerfile,
                "description": "Minimal Ubuntu container with Java",
                "kwargs": {},
            },
            "python": {
                "class": PythonDockerfile,
                "description": "Python-enabled container with virtualenv support",
                "kwargs": {},
            },
            "dbfsfuse": {
                "class": DbfsFuseDockerfile,
                "description": "Python container with DBFS FUSE capabilities",
                "kwargs": {},
            },
            "standard": {
                "class": StandardDockerfile,
                "description": "Standard container with SSH server support",
                "kwargs": {},
            },
            "gpu": {
                "class": GpuDockerfile,
                "description": "GPU-enabled container with CUDA support",
                "kwargs": {
                    "cuda_version": "11.8.0",
                    "cudnn_version": "8",
                    "base_image": "ubuntu:22.04",
                },
            },
        }

    def get_python_versions_from_runtime(self, runtime: Runtime) -> PythonDockerfileVersions:
        """Extract Python version information from runtime to configure containers.

        Args:
            runtime: The runtime object containing environment information

        Returns:
            PythonDockerfileVersions object with extracted version info
        """
        env = runtime.system_environment
        python_version = env.python_version.split()[0] if env.python_version else "3.12"

        # Extract major.minor version (e.g., "3.11" from "3.11.0")
        if "." in python_version:
            parts = python_version.split(".")
            if len(parts) >= 2:
                python_version = f"{parts[0]}.{parts[1]}"

        return PythonDockerfileVersions(python=python_version)

    def generate_dockerfile_for_image_type(self, runtime: Runtime, image_type: str, config: dict[str, Any]) -> str:
        """Generate a Dockerfile for a specific image type and runtime.

        Args:
            runtime: The runtime to build the container for
            image_type: The type of image to build
            config: Configuration for the image type

        Returns:
            The generated Dockerfile content as a string
        """
        self.logger.debug(f"Generating {image_type} image for runtime {runtime.version}")

        # Get the appropriate base image based on runtime requirements
        base_image = "ubuntu:24.04"

        # For GPU images, we need to adjust the base image
        if image_type == "gpu":
            base_image = config["kwargs"].get("base_image", "ubuntu:22.04")

        # Extract Python versions for Python-based images
        kwargs = config["kwargs"].copy()
        if "versions" not in kwargs and image_type in ["python", "dbfsfuse", "standard"]:
            kwargs["versions"] = self.get_python_versions_from_runtime(runtime)

        # Override base image if not already specified
        if "base_image" not in kwargs:
            kwargs["base_image"] = base_image

        # Create the image instance
        image_class = config["class"]
        image_instance = image_class(**kwargs)

        # Generate the Dockerfile
        dockerfile_content = image_instance.render()

        return dockerfile_content

    def save_dockerfile(self, dockerfile_content: str, runtime: Runtime, image_type: str) -> Path:
        """Save a generated Dockerfile to the appropriate location.

        Args:
            dockerfile_content: The Dockerfile content to save
            runtime: The runtime this Dockerfile is for
            image_type: The type of image

        Returns:
            Path to the saved file
        """
        # Create directory structure: data/{image_type}/{runtime_version}/
        runtime_dir = self.data_dir / image_type / runtime.version
        runtime_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename - include ML suffix if it's an ML runtime
        filename = "Dockerfile"
        if runtime.is_ml:
            filename = "Dockerfile.ml"

        dockerfile_path = runtime_dir / filename
        dockerfile_path.write_text(dockerfile_content)

        self.logger.debug("Saved %s Dockerfile for runtime %s to %s", image_type, runtime.version, dockerfile_path)
        return dockerfile_path

    def save_runtime_metadata(self, runtime: Runtime, image_type: str) -> Path:
        """Save runtime metadata as JSON for reference.

        Args:
            runtime: The runtime to save metadata for
            image_type: The type of image this metadata corresponds to

        Returns:
            Path to the saved metadata file
        """
        runtime_dir = self.data_dir / image_type / runtime.version
        runtime_dir.mkdir(parents=True, exist_ok=True)

        release_date = (
            runtime.release_date if isinstance(runtime.release_date, str) else runtime.release_date.isoformat()
        )
        eos_date = (
            runtime.end_of_support_date
            if isinstance(runtime.end_of_support_date, str)
            else runtime.end_of_support_date.isoformat()
        )

        # Prepare metadata
        metadata = {
            "version": runtime.version,
            "release_date": release_date,
            "end_of_support_date": eos_date,
            "spark_version": runtime.spark_version,
            "url": runtime.url,
            "is_ml": runtime.is_ml,
            "is_lts": runtime.is_lts,
            "system_environment": {
                "operating_system": runtime.system_environment.operating_system,
                "java_version": runtime.system_environment.java_version,
                "scala_version": runtime.system_environment.scala_version,
                "python_version": runtime.system_environment.python_version,
                "r_version": runtime.system_environment.r_version,
                "delta_lake_version": runtime.system_environment.delta_lake_version,
            },
            "included_libraries": runtime.included_libraries,
        }

        # Determine filename
        filename = "runtime_metadata.json"
        if runtime.is_ml:
            filename = "runtime_metadata.ml.json"

        metadata_path = runtime_dir / filename
        metadata_path.write_text(json.dumps(metadata, indent=2))

        self.logger.debug("Saved runtime metadata for %s to %s", runtime.version, metadata_path)
        return metadata_path

    def build_all_images_for_runtime(self, runtime: Runtime) -> dict[str, list[Path]]:
        """Build all image variations for a single runtime.

        Args:
            runtime: The runtime to build images for

        Returns:
            Dictionary mapping image types to lists of generated file paths
        """
        self.logger.info(f"Building all image variations for runtime {runtime.version}")
        generated_files = {}

        for image_type, config in self.image_types.items():
            try:
                # Generate Dockerfile
                dockerfile_content = self.generate_dockerfile_for_image_type(runtime, image_type, config)
                dockerfile_path = self.save_dockerfile(dockerfile_content, runtime, image_type)

                # Save metadata
                metadata_path = self.save_runtime_metadata(runtime, image_type)

                generated_files[image_type] = [dockerfile_path, metadata_path]

                self.logger.info(f"Generated {image_type} image for runtime {runtime.version}")

            except Exception:
                self.logger.exception("Failed to generate %s image for runtime %s", image_type, runtime.version)
                generated_files[image_type] = []

        return generated_files

    def build_all_images_for_all_runtimes(self) -> dict[str, dict[str, list[Path]]]:
        """Build all image variations for all available runtimes.

        Returns:
            Nested dictionary: {runtime_version: {image_type: [file_paths]}}
        """
        self.logger.info("Starting to build all images for all runtimes")

        # Get all supported runtimes
        runtimes = self.scraper.get_supported_runtimes()
        if not runtimes:
            self.logger.error("No runtimes found")
            return {}

        self.logger.info(f"Found {len(runtimes)} runtimes to process")

        all_generated_files = {}

        for runtime in runtimes:
            runtime_key = f"{runtime.version}{'_ml' if runtime.is_ml else ''}"
            generated_files = self.build_all_images_for_runtime(runtime)
            all_generated_files[runtime_key] = generated_files

        # Save summary report
        self.save_build_summary(all_generated_files)

        self.logger.info(f"Completed building images for {len(runtimes)} runtimes")
        return all_generated_files

    def save_build_summary(self, all_generated_files: dict[str, dict[str, list[Path]]]) -> Path:
        """Save a summary of all generated files.

        Args:
            all_generated_files: The complete mapping of generated files

        Returns:
            Path to the saved summary file
        """
        summary = {
            "total_runtimes": len(all_generated_files),
            "image_types": list(self.image_types.keys()),
            "total_files_generated": sum(
                len(files) for runtime_files in all_generated_files.values() for files in runtime_files.values()
            ),
            "build_details": {
                runtime: {image_type: [str(path) for path in paths] for image_type, paths in runtime_files.items()}
                for runtime, runtime_files in all_generated_files.items()
            },
        }

        summary_path = self.data_dir / "build_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"Saved build summary to {summary_path}")
        return summary_path

    def run(self) -> dict[str, dict[str, list[Path]]]:
        """Main entry point to run the complete engine process.

        Returns:
            Dictionary mapping runtime versions to generated files
        """
        self.logger.info("Starting ContainerEngine run")
        result = self.build_all_images_for_all_runtimes()
        self.logger.info("ContainerEngine run completed")
        return result


def main() -> None:
    """Main function to run the container engine."""
    engine = RuntimeContainerEngine()
    engine.run()


if __name__ == "__main__":
    main()
