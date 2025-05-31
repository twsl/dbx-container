import json
from pathlib import Path
from typing import Any

from rich.panel import Panel

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
        data_dir: Path | str = Path("./data"),
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
        self.data_dir = Path(data_dir) if isinstance(data_dir, str) else data_dir
        self.scraper = RuntimeScraper(max_workers=max_workers, verify_ssl=verify_ssl)

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

    def extract_os_version_from_runtime(self, runtime: Runtime) -> str:
        """Extract OS version information from runtime.

        Args:
            runtime: The runtime object containing environment information

        Returns:
            Ubuntu version string (e.g., "22.04", "24.04")
        """
        env = runtime.system_environment
        if not env.operating_system:
            return "24.04"  # Default to latest LTS

        os_info = env.operating_system.lower()

        # Extract Ubuntu version from strings like "Ubuntu 22.04.3 LTS" or "Ubuntu 24.04"
        if "ubuntu" in os_info:
            parts = os_info.split()
            for part in parts:
                if "." in part and any(char.isdigit() for char in part):
                    # Extract major.minor version (e.g., "22.04" from "22.04.3")
                    version_parts = part.split(".")
                    if len(version_parts) >= 2:
                        try:
                            major = int(version_parts[0])
                            minor = int(version_parts[1])
                        except ValueError:
                            continue
                        else:
                            return f"{major}.{minor:02d}"

        # Default to latest LTS if can't parse
        return "24.04"

    def get_runtime_variations(self, runtime: Runtime) -> list[dict[str, str]]:
        """Get all OS and Python version variations for a runtime.

        Args:
            runtime: The runtime object

        Returns:
            List of variation configurations with os_version and python_version
        """
        os_version = self.extract_os_version_from_runtime(runtime)
        python_versions = self.get_python_versions_from_runtime(runtime)

        # For now, we'll create variations based on the runtime's actual versions
        # In the future, this could be expanded to include multiple variations
        variations = [
            {
                "os_version": os_version,
                "python_version": python_versions.python,
                "suffix": f"ubuntu{os_version.replace('.', '')}-py{python_versions.python.replace('.', '')}",
            }
        ]

        # Add common variations for LTS runtimes
        if runtime.is_lts:
            # Add Ubuntu 22.04 variation if the runtime uses 24.04
            if os_version == "24.04":
                variations.append(
                    {
                        "os_version": "22.04",
                        "python_version": python_versions.python,
                        "suffix": f"ubuntu2204-py{python_versions.python.replace('.', '')}",
                    }
                )
            # Add Ubuntu 24.04 variation if the runtime uses 22.04
            elif os_version == "22.04":
                variations.append(
                    {
                        "os_version": "24.04",
                        "python_version": python_versions.python,
                        "suffix": f"ubuntu2404-py{python_versions.python.replace('.', '')}",
                    }
                )

        return variations

    def generate_dockerfile_for_image_type(
        self, runtime: Runtime, image_type: str, config: dict[str, Any], variation: dict[str, str] | None = None
    ) -> str:
        """Generate a Dockerfile for a specific image type and runtime.

        Args:
            runtime: The runtime to build the container for
            image_type: The type of image to build
            config: Configuration for the image type
            variation: Optional variation config with os_version and python_version

        Returns:
            The generated Dockerfile content as a string
        """
        self.logger.debug(f"Generating {image_type} image for runtime {runtime.version}")

        # Get the appropriate base image based on runtime requirements or variation
        base_image = f"ubuntu:{variation['os_version']}" if variation else "ubuntu:24.04"

        # For GPU images, we need to adjust the base image
        if image_type == "gpu":
            if variation:
                base_image = f"ubuntu:{variation['os_version']}"
            else:
                base_image = config["kwargs"].get("base_image", "ubuntu:22.04")

        # Extract Python versions for Python-based images
        kwargs = config["kwargs"].copy()
        if "versions" not in kwargs and image_type in ["python", "dbfsfuse", "standard"]:
            if variation:
                # Use variation-specific Python version
                kwargs["versions"] = PythonDockerfileVersions(python=variation["python_version"])
            else:
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

    def save_dockerfile(
        self, dockerfile_content: str, runtime: Runtime, image_type: str, variation: dict[str, str] | None = None
    ) -> Path:
        """Save a generated Dockerfile to the appropriate location.

        Args:
            dockerfile_content: The Dockerfile content to save
            runtime: The runtime this Dockerfile is for
            image_type: The type of image
            variation: Optional variation config for naming

        Returns:
            Path to the saved file
        """
        # Create directory structure: data/{image_type}/{runtime_version}[_variation]/
        runtime_version = runtime.version
        if variation:
            runtime_version = f"{runtime.version}_{variation['suffix']}"

        runtime_dir = self.data_dir / image_type / runtime_version
        runtime_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename - include ML suffix if it's an ML runtime
        filename = "Dockerfile"
        if runtime.is_ml:
            filename = "Dockerfile.ml"

        dockerfile_path = runtime_dir / filename
        dockerfile_path.write_text(dockerfile_content)

        variation_info = f" ({variation['suffix']})" if variation else ""
        self.logger.debug(
            f"Saved {image_type} Dockerfile for runtime {runtime.version}{variation_info} to {dockerfile_path}"
        )
        return dockerfile_path

    def save_runtime_metadata(self, runtime: Runtime, image_type: str, variation: dict[str, str] | None = None) -> Path:
        """Save runtime metadata as JSON for reference.

        Args:
            runtime: The runtime to save metadata for
            image_type: The type of image this metadata corresponds to
            variation: Optional variation config for naming

        Returns:
            Path to the saved metadata file
        """
        runtime_version = runtime.version
        if variation:
            runtime_version = f"{runtime.version}_{variation['suffix']}"

        runtime_dir = self.data_dir / image_type / runtime_version
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

        # Add variation-specific metadata
        if variation:
            metadata["variation"] = {
                "os_version": variation["os_version"],
                "python_version": variation["python_version"],
                "suffix": variation["suffix"],
            }

        # Determine filename
        filename = "runtime_metadata.json"
        if runtime.is_ml:
            filename = "runtime_metadata.ml.json"

        metadata_path = runtime_dir / filename
        metadata_path.write_text(json.dumps(metadata, indent=2))

        variation_info = f" ({variation['suffix']})" if variation else ""
        self.logger.debug(f"Saved runtime metadata for {runtime.version}{variation_info} to {metadata_path}")
        return metadata_path
        if runtime.is_ml:
            filename = "runtime_metadata.ml.json"

        metadata_path = runtime_dir / filename
        metadata_path.write_text(json.dumps(metadata, indent=2))

        self.logger.debug(f"Saved runtime metadata for {runtime.version} to {metadata_path}")
        return metadata_path

    def build_all_images_for_runtime(self, runtime: Runtime) -> dict[str, list[Path]]:
        """Build all image variations for a single runtime.

        Args:
            runtime: The runtime to build images for

        Returns:
            Dictionary mapping image types to lists of generated file paths
        """
        runtime_display = f"[bold blue]{runtime.version}[/bold blue]"
        if runtime.is_ml:
            runtime_display += " [yellow](ML)[/yellow]"
        if runtime.is_lts:
            runtime_display += " [green](LTS)[/green]"

        self.logger.print(f"\n🔨 Building images for runtime {runtime_display}")
        generated_files = {}

        # Only build runtime variations for python and gpu image types
        runtime_specific_types = ["python", "gpu"]

        # Filter image types to only those that need runtime variations
        filtered_image_types = {k: v for k, v in self.image_types.items() if k in runtime_specific_types}

        # Get all variations for this runtime
        variations = self.get_runtime_variations(runtime)

        # Use rich track for progress indication
        for image_type, config in self.logger.progress(
            filtered_image_types.items(), description=f"Generating {runtime.version}"
        ):
            generated_files[image_type] = []

            try:
                # Build images for each variation
                for variation in variations:
                    try:
                        # Generate Dockerfile
                        dockerfile_content = self.generate_dockerfile_for_image_type(
                            runtime, image_type, config, variation
                        )
                        dockerfile_path = self.save_dockerfile(dockerfile_content, runtime, image_type, variation)

                        # Save metadata
                        metadata_path = self.save_runtime_metadata(runtime, image_type, variation)

                        generated_files[image_type].extend([dockerfile_path, metadata_path])

                        # Minimal success indication (no permanent log entry)
                        # Just log debug message instead of print
                        self.logger.debug(f"Generated {image_type} image for variation {variation['suffix']}")

                    except Exception:
                        self.logger.exception(
                            f"Failed to generate {image_type} image for runtime {runtime.version} variation {variation['suffix']}"
                        )

            except Exception:
                self.logger.exception(f"Failed to generate {image_type} image for runtime {runtime.version}")

        return generated_files

    def build_non_runtime_specific_images(self, reference_runtime: Runtime) -> dict[str, list[Path]]:
        """Build image types that don't need runtime variations.

        Args:
            reference_runtime: A reference runtime to use for base configuration

        Returns:
            Dictionary mapping image types to lists of generated file paths
        """
        self.logger.print("\n🔨 Building non-runtime-specific images")
        generated_files = {}

        # Image types that don't need runtime variations
        non_runtime_types = ["minimal", "dbfsfuse", "standard"]

        # Filter image types to only those that don't need runtime variations
        filtered_image_types = {k: v for k, v in self.image_types.items() if k in non_runtime_types}

        # Use rich track for progress indication
        for image_type, config in self.logger.progress(
            filtered_image_types.items(), description="Generating non-runtime-specific images"
        ):
            try:
                # Generate Dockerfile using reference runtime
                dockerfile_content = self.generate_dockerfile_for_image_type(reference_runtime, image_type, config)

                # Save to a generic location without runtime version
                base_dir = self.data_dir / image_type / "latest"
                base_dir.mkdir(parents=True, exist_ok=True)

                dockerfile_path = base_dir / "Dockerfile"
                dockerfile_path.write_text(dockerfile_content)

                # Save metadata
                metadata_path = self.save_runtime_metadata_generic(reference_runtime, image_type)

                generated_files[image_type] = [dockerfile_path, metadata_path]

                self.logger.debug(f"Generated {image_type} image (non-runtime-specific)")

            except Exception:
                self.logger.exception(f"Failed to generate {image_type} image (non-runtime-specific)")
                generated_files[image_type] = []

        self.logger.info(f"Successfully generated {len(filtered_image_types.items())} images")
        return generated_files

    def save_runtime_metadata_generic(self, runtime: Runtime, image_type: str) -> Path:
        """Save generic runtime metadata for non-runtime-specific images.

        Args:
            runtime: The reference runtime used for metadata
            image_type: The type of image this metadata corresponds to

        Returns:
            Path to the saved metadata file
        """
        base_dir = self.data_dir / image_type / "latest"
        base_dir.mkdir(parents=True, exist_ok=True)

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
            "note": "This is a generic image not tied to a specific runtime version",
            "reference_runtime_version": runtime.version,
            "reference_release_date": release_date,
            "reference_end_of_support_date": eos_date,
            "reference_spark_version": runtime.spark_version,
            "reference_url": runtime.url,
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

        metadata_path = base_dir / "runtime_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))

        self.logger.debug(f"Saved generic runtime metadata for {image_type} to {metadata_path}")
        return metadata_path

    def build_all_images_for_all_runtimes(self) -> dict[str, dict[str, list[Path]]]:
        """Build all image variations for all available runtimes.

        Returns:
            Nested dictionary: {runtime_version: {image_type: [file_paths]}}
        """
        # Display a nice header
        self.logger.print(
            Panel(
                "[bold green]🚀 DBX Container Builder[/bold green]\nBuilding Dockerfiles for all Databricks runtimes",
                expand=False,
                border_style="green",
            )
        )

        # Get all supported runtimes
        with self.logger.status("[bold green]Fetching runtime information..."):
            runtimes = self.scraper.get_supported_runtimes()

        if not runtimes:
            self.logger.error("No runtimes found")
            return {}

        self.logger.print(f"\n[bold cyan]📋 Processing {len(runtimes)} runtimes[/bold cyan]")

        all_generated_files = {}

        # Build non-runtime-specific images once using the first runtime as reference
        if runtimes:
            reference_runtime = runtimes[0]
            non_runtime_files = self.build_non_runtime_specific_images(reference_runtime)
            all_generated_files["non_runtime_specific"] = non_runtime_files

        # Use rich track for overall progress
        for runtime in self.logger.progress(runtimes, description="Processing runtimes"):
            runtime_key = f"{runtime.version}{'_ml' if runtime.is_ml else ''}"
            generated_files = self.build_all_images_for_runtime(runtime)
            all_generated_files[runtime_key] = generated_files

        # Save summary report
        self.save_build_summary(all_generated_files)

        # Final summary
        total_files = sum(
            len(files) for runtime_files in all_generated_files.values() for files in runtime_files.values()
        )

        self.logger.print(
            Panel(
                f"[bold green]✅ Build Complete![/bold green]\n"
                f"Generated [bold cyan]{total_files}[/bold cyan] files for "
                f"[bold cyan]{len(runtimes)}[/bold cyan] runtimes",
                expand=False,
                border_style="green",
            )
        )

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
