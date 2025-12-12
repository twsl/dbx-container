from datetime import date
import json
from pathlib import Path
from typing import Any

from rich.panel import Panel

from dbx_container.data.scraper import RuntimeScraper
from dbx_container.images.gpu import GpuDockerfile
from dbx_container.images.minimal import MinimalUbuntuDockerfile
from dbx_container.images.python import PythonDockerfile, PythonDockerfileVersions
from dbx_container.images.standard import StandardDockerfile
from dbx_container.models.environment import SystemEnvironment
from dbx_container.models.runtime import Runtime
from dbx_container.utils.logging import get_logger


class RuntimeContainerEngine:
    """Engine for building container variations across all Databricks runtimes."""

    def __init__(
        self,
        data_dir: Path | str = Path("./data"),
        max_workers: int = 5,
        verify_ssl: bool = False,
        latest_lts_count: int | None = 2,
        force_ubuntu_version: str | None = None,
        skip_ml_variants: bool = True,
    ) -> None:
        """Initialize the ContainerEngine.

        Args:
            data_dir: Directory where to save generated files
            max_workers: Maximum number of worker threads for scraping
            verify_ssl: Whether to verify SSL certificates when making HTTP requests
            latest_lts_count: Number of latest LTS versions to build (None for all LTS versions, default: 2)
            force_ubuntu_version: Force a specific Ubuntu version for all base images (e.g., "22.04").
                                  If None, defaults to "24.04" unless matching runtime's OS version.
            skip_ml_variants: Skip ML runtime variants during generation (default: True)
        """
        self.logger = get_logger(self.__class__.__name__)
        self.data_dir = Path(data_dir) if isinstance(data_dir, str) else data_dir
        self.scraper = RuntimeScraper(max_workers=max_workers, verify_ssl=verify_ssl)
        self.latest_lts_count = latest_lts_count
        self.force_ubuntu_version = force_ubuntu_version
        self.skip_ml_variants = skip_ml_variants

        # Store workspace root for relative path calculations
        # Find the project root by looking for pyproject.toml
        self.workspace_root = Path.cwd()
        for parent in [Path.cwd()] + list(Path.cwd().parents):
            if (parent / "pyproject.toml").exists():
                self.workspace_root = parent
                break

        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)

        # Image type configurations with dependency chains
        # Standard chain: minimal -> standard -> python
        # GPU chain: nvidia/cuda -> minimal-gpu -> standard-gpu -> python-gpu
        # Standalone GPU: nvidia/cuda -> gpu
        self.image_types = {
            "gpu": {
                "class": GpuDockerfile,
                "description": "Standalone GPU-enabled container with CUDA support",
                "kwargs": {},
                "depends_on": None,  # Standalone, uses nvidia/cuda directly
                "runtime_specific": False,  # Does not need runtime-specific builds
            },
            "minimal": {
                "class": MinimalUbuntuDockerfile,
                "description": "Minimal Ubuntu 24.04 LTS container with Java",
                "kwargs": {},
                "depends_on": None,  # Base image, no dependencies
                "runtime_specific": False,
            },
            "minimal-gpu": {
                "class": MinimalUbuntuDockerfile,
                "description": "Minimal GPU container with CUDA and Java",
                "kwargs": {"use_gpu_base": True},
                "depends_on": "gpu",  # Depends on gpu base image
                "runtime_specific": False,
            },
            "standard": {
                "class": StandardDockerfile,
                "description": "Standard container with FUSE and SSH server support",
                "kwargs": {},
                "depends_on": "minimal",
                "runtime_specific": False,  # Does not need runtime-specific builds
            },
            "standard-gpu": {
                "class": StandardDockerfile,
                "description": "GPU standard container with FUSE and SSH support",
                "kwargs": {"use_gpu_base": True},
                "depends_on": "minimal-gpu",
                "runtime_specific": False,  # Does not need runtime-specific builds
            },
            "python": {
                "class": PythonDockerfile,
                "description": "Python-enabled container with virtualenv support",
                "kwargs": {},
                "depends_on": "standard",
                "runtime_specific": True,  # Needs runtime-specific requirements.txt
            },
            "python-gpu": {
                "class": PythonDockerfile,
                "description": "GPU Python container with CUDA support",
                "kwargs": {"use_gpu_base": True},
                "depends_on": "standard-gpu",
                "runtime_specific": True,  # Needs runtime-specific requirements.txt
            },
        }

    def get_dependency_image_reference(
        self,
        image_type: str,
        runtime: Runtime | None = None,
        variation: dict[str, str] | None = None,
        registry: str | None = None,
        use_gpu_base: bool = False,
    ) -> str:
        """Get the image reference for the dependency of a given image type.

        Args:
            image_type: The image type to get the dependency for
            runtime: The runtime (if runtime-specific)
            variation: The variation config (if applicable)
            registry: Registry prefix (e.g., 'ghcr.io/owner/dbx-runtime'). If None, uses local tag.
            use_gpu_base: Whether to use GPU variant base images

        Returns:
            Full image reference to use as FROM base
        """
        config = self.image_types.get(image_type)
        if not config or not config["depends_on"]:
            # No dependency, use default base image
            # Check if variation specifies a different OS version
            if variation and "os_version" in variation:
                os_version = variation["os_version"]
                if os_version != "24.04":
                    self.logger.warning(
                        f"Runtime uses Ubuntu {os_version}, but upgrading to 24.04 for base image. "
                        f"To use Ubuntu {os_version}, explicitly configure it in the build chain."
                    )
                # Default to 24.04 unless explicitly configured otherwise
                return "ubuntu:24.04"
            return "ubuntu:24.04"

        depends_on = config["depends_on"]
        dep_config = self.image_types.get(depends_on)

        # Build the image tag using new naming convention: dbx-runtime:type-tag
        # The depends_on already includes -gpu suffix if needed (e.g., "python-gpu")
        dep_name = depends_on

        # For python images (and their GPU variants), include python version in tag
        # Check the base type (without -gpu suffix)
        base_dep_type = depends_on.replace("-gpu", "")
        if base_dep_type == "python" and variation:
            python_version = variation["python_version"].replace(".", "")
            dep_name = f"{dep_name}-py{python_version}"

        # Format the image reference based on whether registry is provided
        # If registry is None, use local tag format (dbx-runtime:tag)
        # If registry is provided, use registry:tag format
        image_ref = f"dbx-runtime:{dep_name}" if registry is None else f"{registry}:{dep_name}"

        # If dependency is runtime-specific and we have runtime info, include it
        if dep_config and dep_config.get("runtime_specific") and runtime:
            runtime_clean = runtime.version.replace(" ", "-").replace("(", "").replace(")", "").lower()
            image_ref = f"{image_ref}:{runtime_clean}"
            if variation:
                image_ref = f"{image_ref}-{variation['suffix']}"
            if runtime.is_ml:
                image_ref = f"{image_ref}-ml"

        return image_ref

    def should_upgrade_os_version(self, variation: dict[str, str] | None) -> tuple[bool, str]:
        """Check if OS version should be upgraded to default (24.04).

        Args:
            variation: The variation config with os_version

        Returns:
            Tuple of (should_upgrade, os_version_to_use)
        """
        # If force_ubuntu_version is set, use it
        if self.force_ubuntu_version:
            return False, self.force_ubuntu_version

        if not variation or "os_version" not in variation:
            return False, "24.04"

        os_version = variation["os_version"]
        default_os = "24.04"

        if os_version != default_os:
            # By default, upgrade to latest LTS (24.04)
            return True, default_os

        return False, os_version

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

    @staticmethod
    def sanitize_runtime_version(version: str) -> str:
        """Sanitize runtime version by replacing whitespace with dashes.

        Args:
            version: The runtime version string (e.g., "15.4 LTS")

        Returns:
            Sanitized version string (e.g., "15.4-LTS")
        """
        return version.replace(" ", "-")

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
                "separator": "-",  # Separator between runtime version and suffix
            }
        ]

        return variations

    def generate_dockerfile_for_image_type(
        self,
        runtime: Runtime,
        image_type: str,
        config: dict[str, Any],
        variation: dict[str, str] | None = None,
        registry: str | None = None,
    ) -> str:
        """Generate a Dockerfile for a specific image type and runtime.

        Args:
            runtime: The runtime to build the container for
            image_type: The type of image to build
            config: Configuration for the image type
            variation: Optional variation config with os_version and python_version
            registry: Optional registry prefix for image naming

        Returns:
            The generated Dockerfile content as a string
        """
        self.logger.debug(f"Generating {image_type} image for runtime {runtime.version}")

        # Determine if this is a GPU variant
        use_gpu_base = config["kwargs"].get("use_gpu_base", False)

        # Get the appropriate base image based on dependency chain
        # Check if this image type depends on another locally-built image
        base_image = None
        if config.get("depends_on"):
            # Use the dependency image as base
            base_image = self.get_dependency_image_reference(image_type, runtime, variation, registry, use_gpu_base)

        runtime_specific = [k for k, v in self.image_types.items() if v["runtime_specific"]]

        # Extract Python versions for Python-based images
        kwargs = config["kwargs"].copy()
        if "versions" not in kwargs and image_type in runtime_specific:
            if variation:
                # Use variation-specific Python version
                kwargs["versions"] = PythonDockerfileVersions(python=variation["python_version"])
            else:
                kwargs["versions"] = self.get_python_versions_from_runtime(runtime)

        # Handle OS version for base images (minimal, minimal-gpu, standard, standard-gpu)
        # Check if we need to build with a specific OS version
        if image_type in ["minimal", "minimal-gpu", "standard", "standard-gpu"] and variation:
            should_upgrade, os_version_to_use = self.should_upgrade_os_version(variation)
            runtime_os = variation.get("os_version", "24.04")

            if should_upgrade:
                # Notify user that we're upgrading OS version
                self.logger.info(
                    f"🔄 Runtime {runtime.version} uses Ubuntu {runtime_os}, "
                    f"automatically upgrading base images to Ubuntu {os_version_to_use}"
                )
            elif runtime_os != "24.04":
                # Explicitly configured to use non-default OS
                self.logger.info(f"📦 Building {image_type} with Ubuntu {runtime_os} as explicitly configured")
                os_version_to_use = runtime_os

            # Pass ubuntu_version to minimal/minimal-gpu and standard/standard-gpu images
            if image_type in ["minimal", "minimal-gpu", "standard", "standard-gpu"]:
                kwargs["ubuntu_version"] = os_version_to_use

        # Override base image if not already specified and we have a dependency
        # For images without dependencies (minimal, minimal-gpu), let the class handle the base image
        if "base_image" not in kwargs and base_image is not None:
            kwargs["base_image"] = base_image

        # Pass registry to image constructor
        # If registry is None, pass None (for local Docker builds without registry prefix)
        # The image classes will handle None registry appropriately
        kwargs["registry"] = registry

        # Pass runtime to image constructor for metadata labels
        # Only python and python-gpu images accept runtime parameter
        if image_type in runtime_specific:
            kwargs["runtime"] = runtime

            # Generate requirements.txt and pass the path
            # The path needs to be relative to the build context (project root)
            # Generate the requirements.txt file
            requirements_abs_path = self.generate_requirements_txt(runtime, image_type, variation)

            # Convert to relative path if it's absolute, otherwise use as-is
            if requirements_abs_path.is_absolute():
                try:
                    requirements_rel_path = str(requirements_abs_path.relative_to(Path.cwd()))
                except ValueError:
                    # If the path is not relative to cwd, use the absolute path
                    requirements_rel_path = str(requirements_abs_path)
            else:
                requirements_rel_path = str(requirements_abs_path)

            kwargs["requirements_path"] = requirements_rel_path

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
        # Create directory structure: data/{image_type}/{runtime_version}[-variation][-ml]/
        runtime_version = self.sanitize_runtime_version(runtime.version)
        if variation:
            separator = variation.get("separator", "-")
            runtime_version = f"{runtime_version}{separator}{variation['suffix']}"
        if runtime.is_ml:
            runtime_version = f"{runtime_version}-ml"

        runtime_dir = self.data_dir / image_type / runtime_version
        runtime_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename - always use "Dockerfile" now that ML variants have their own folder
        filename = "Dockerfile"

        dockerfile_path = runtime_dir / filename
        dockerfile_path.write_text(dockerfile_content)

        variation_info = f" ({variation['suffix']})" if variation else ""
        self.logger.debug(
            f"Saved {image_type} Dockerfile for runtime {runtime.version}{variation_info} to {dockerfile_path}"
        )
        return dockerfile_path

    def generate_requirements_txt(
        self, runtime: Runtime, image_type: str, variation: dict[str, str] | None = None
    ) -> Path:
        """Generate requirements.txt from runtime's included libraries.

        Args:
            runtime: The runtime with included_libraries data
            image_type: The type of image (should be python or python-gpu)
            variation: Optional variation config for naming

        Returns:
            Path to the generated requirements.txt file
        """
        runtime_version = self.sanitize_runtime_version(runtime.version)
        if variation:
            separator = variation.get("separator", "-")
            runtime_version = f"{runtime_version}{separator}{variation['suffix']}"
        if runtime.is_ml:
            runtime_version = f"{runtime_version}-ml"

        runtime_dir = self.data_dir / image_type / runtime_version
        runtime_dir.mkdir(parents=True, exist_ok=True)

        requirements_path = runtime_dir / "requirements.txt"

        # Generate requirements from included_libraries
        python_libs = runtime.included_libraries.get("python", {})

        # Write requirements.txt
        with requirements_path.open("w") as f:
            f.write("# Python requirements for Databricks runtime\n")
            f.write(f"# Runtime version: {runtime.version}\n")
            f.write("# Generated from included_libraries\n\n")

            # Sort libraries alphabetically for consistency
            for lib_name, lib_version in sorted(python_libs.items()):
                # Handle both string versions and tuple (version, channel) format
                version = lib_version[0] if isinstance(lib_version, tuple) else lib_version
                f.write(f"{lib_name}=={version}\n")

        self.logger.debug(f"Generated requirements.txt with {len(python_libs)} packages for {runtime.version}")
        return requirements_path

    def save_runtime_metadata(self, runtime: Runtime, image_type: str, variation: dict[str, str] | None = None) -> Path:
        """Save runtime metadata as JSON for reference.

        Args:
            runtime: The runtime to save metadata for
            image_type: The type of image this metadata corresponds to
            variation: Optional variation config for naming

        Returns:
            Path to the saved metadata file
        """
        runtime_version = self.sanitize_runtime_version(runtime.version)
        if variation:
            separator = variation.get("separator", "-")
            runtime_version = f"{runtime_version}{separator}{variation['suffix']}"
        if runtime.is_ml:
            runtime_version = f"{runtime_version}-ml"

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

        # Determine filename - always use "runtime_metadata.json" now that ML variants have their own folder
        filename = "runtime_metadata.json"

        metadata_path = runtime_dir / filename
        metadata_path.write_text(json.dumps(metadata, indent=2))

        variation_info = f" ({variation['suffix']})" if variation else ""
        self.logger.debug(f"Saved runtime metadata for {runtime.version}{variation_info} to {metadata_path}")
        return metadata_path

    def build_all_images_for_runtime(self, runtime: Runtime, registry: str | None = None) -> dict[str, list[Path]]:
        """Build all image variations for a single runtime.

        Args:
            runtime: The runtime to build images for
            registry: Optional registry prefix for image naming

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

        # Get all variations for this runtime
        variations = self.get_runtime_variations(runtime)

        # Check if we need to build OS-specific base images (minimal, standard)
        # This happens when the runtime uses a different OS version or force_ubuntu_version is set
        for variation in variations:
            should_upgrade, os_version_to_use = self.should_upgrade_os_version(variation)
            runtime_os = variation.get("os_version", "24.04")

            # Build OS-specific base images if needed
            if runtime_os != "24.04" or self.force_ubuntu_version:
                # Build minimal and standard images with the specific OS version
                for base_type in ["minimal", "standard"]:
                    # Also build GPU variants if they're in the dependency chain
                    for use_gpu in [False, True]:
                        image_type = f"{base_type}-gpu" if use_gpu else base_type
                        config = self.image_types.get(image_type)

                        if not config:
                            continue

                        try:
                            # Create a minimal dummy runtime for base images
                            dummy_runtime = Runtime(
                                version="generic",
                                release_date=date.today(),
                                end_of_support_date=date.today(),
                                spark_version="N/A",
                                url="",
                                is_ml=False,
                                is_lts=False,
                                system_environment=SystemEnvironment(
                                    operating_system=f"Ubuntu {os_version_to_use} LTS",
                                    java_version="N/A",
                                    scala_version="N/A",
                                    python_version="N/A",
                                    r_version="N/A",
                                    delta_lake_version="N/A",
                                ),
                                included_libraries={},
                            )

                            # Generate Dockerfile with OS-specific version
                            dockerfile_content = self.generate_dockerfile_for_image_type(
                                dummy_runtime, image_type, config, variation, registry
                            )

                            # Save to OS-specific directory
                            # Ubuntu 24.04 goes to "latest", other versions get their own folder
                            if os_version_to_use == "24.04":
                                os_dir = self.data_dir / image_type / "latest"
                            else:
                                os_dir = self.data_dir / image_type / f"ubuntu{os_version_to_use.replace('.', '')}"
                            os_dir.mkdir(parents=True, exist_ok=True)
                            dockerfile_path = os_dir / "Dockerfile"
                            dockerfile_path.write_text(dockerfile_content)

                            self.logger.debug(f"Generated {image_type} base image for Ubuntu {os_version_to_use}")

                        except Exception:
                            self.logger.exception(
                                f"Failed to generate {image_type} base image for Ubuntu {os_version_to_use}"
                            )

        # Build runtime-specific images: python chain (standard -> python)
        runtime_specific_types = [k for k, v in self.image_types.items() if v["runtime_specific"]]

        # Filter image types to only those that need runtime variations
        filtered_image_types = {k: v for k, v in self.image_types.items() if k in runtime_specific_types}

        # Use rich track for progress indication
        for image_type, config in self.logger.progress(
            filtered_image_types.items(), description=f"Generating {runtime.version}"
        ):
            generated_files[image_type] = []

            try:
                # Build images for each variation
                for variation in variations:
                    try:
                        # Generate Dockerfile (requirements.txt is generated inside for python images)
                        dockerfile_content = self.generate_dockerfile_for_image_type(
                            runtime, image_type, config, variation, registry
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

    def build_non_runtime_specific_images(self, registry: str | None = None) -> dict[str, list[Path]]:
        """Build image types that don't need runtime variations.

        Args:
            registry: Optional registry prefix for image naming

        Returns:
            Dictionary mapping image types to lists of generated file paths
        """
        self.logger.print("\n🔨 Building non-runtime-specific images")
        generated_files = {}

        # Image types that don't need runtime variations
        non_runtime_types = [k for k, v in self.image_types.items() if not v["runtime_specific"]]

        # Filter image types to only those that don't need runtime variations
        filtered_image_types = {k: v for k, v in self.image_types.items() if k in non_runtime_types}

        # Use rich track for progress indication
        for image_type, config in self.logger.progress(
            filtered_image_types.items(), description="Generating non-runtime-specific images"
        ):
            try:
                # Generate Dockerfile without runtime-specific configuration
                # Create a minimal Runtime object for the method signature (minimal images don't use it)
                dummy_runtime = Runtime(
                    version="generic",
                    release_date=date.today(),
                    end_of_support_date=date.today(),
                    spark_version="N/A",
                    url="",
                    is_ml=False,
                    is_lts=False,
                    system_environment=SystemEnvironment(
                        operating_system="Ubuntu 24.04 LTS",
                        java_version="N/A",
                        scala_version="N/A",
                        python_version="N/A",
                        r_version="N/A",
                        delta_lake_version="N/A",
                    ),
                    included_libraries={},
                )

                dockerfile_content = self.generate_dockerfile_for_image_type(
                    dummy_runtime, image_type, config, variation=None, registry=registry
                )

                # Save to a generic location without runtime version
                base_dir = self.data_dir / image_type / "latest"
                base_dir.mkdir(parents=True, exist_ok=True)

                dockerfile_path = base_dir / "Dockerfile"
                dockerfile_path.write_text(dockerfile_content)

                generated_files[image_type] = [dockerfile_path]

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

    def _filter_latest_lts_runtimes(self, runtimes: list[Runtime], count: int) -> list[Runtime]:
        """Filter to only the latest N LTS versions.

        Args:
            runtimes: List of all runtimes
            count: Number of latest LTS versions to keep

        Returns:
            Filtered list containing only the latest N LTS versions (base and ML variants)
        """
        # Group LTS runtimes by version (base and ML together)
        lts_versions = {}
        for runtime in runtimes:
            if runtime.is_lts:
                # Use version without ML suffix as key
                version_key = runtime.version
                if version_key not in lts_versions:
                    lts_versions[version_key] = []
                lts_versions[version_key].append(runtime)

        # Sort versions by release date (most recent first)
        sorted_versions = sorted(
            lts_versions.items(),
            key=lambda x: x[1][0].release_date if x[1] else "",
            reverse=True,
        )

        # Take the latest N versions
        latest_versions = sorted_versions[:count]

        # Flatten the list to include all variants (base and ML) of selected versions
        filtered_runtimes = []
        selected_versions = set()
        for version, runtime_list in latest_versions:
            if self.skip_ml_variants:
                # Only include non-ML variants
                filtered_runtimes.extend([r for r in runtime_list if not r.is_ml])
            else:
                filtered_runtimes.extend(runtime_list)
            selected_versions.add(version)

        # Log which versions were selected
        if selected_versions:
            version_list = ", ".join(sorted(selected_versions))
            self.logger.info(f"Building latest {count} LTS versions: {version_list}")

        return filtered_runtimes

    def build_all_images_for_all_runtimes(self, registry: str | None = None) -> dict[str, dict[str, list[Path]]]:
        """Build all image variations for all available runtimes.

        Args:
            registry: Optional registry prefix for image naming

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

        # Filter to latest LTS versions if configured
        if self.latest_lts_count is not None:
            runtimes = self._filter_latest_lts_runtimes(runtimes, self.latest_lts_count)
            self.logger.print(
                f"\n[bold cyan]📋 Processing {len(runtimes)} runtimes "
                f"(latest {self.latest_lts_count} LTS versions)[/bold cyan]"
            )
        else:
            self.logger.print(f"\n[bold cyan]📋 Processing {len(runtimes)} runtimes[/bold cyan]")

        all_generated_files = {}

        # Build non-runtime-specific images once
        non_runtime_files = self.build_non_runtime_specific_images(registry)
        all_generated_files["non_runtime_specific"] = non_runtime_files

        # Use rich track for overall progress
        for runtime in self.logger.progress(runtimes, description="Processing runtimes"):
            runtime_key = f"{runtime.version}{'_ml' if runtime.is_ml else ''}"
            generated_files = self.build_all_images_for_runtime(runtime, registry)
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
                runtime: {
                    image_type: [str(path.absolute().relative_to(self.workspace_root)) for path in paths]
                    for image_type, paths in runtime_files.items()
                }
                for runtime, runtime_files in all_generated_files.items()
            },
        }

        summary_path = self.data_dir / "build_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))

        self.logger.info(f"Saved build summary to {summary_path}")
        return summary_path

    def generate_build_matrix(
        self,
        only_lts: bool = False,
        image_type: str | None = None,
        latest_lts_count: int | None = None,
    ) -> dict:
        """Generate a GitHub Actions build matrix from the build summary.

        Args:
            only_lts: If True, only include LTS runtimes
            image_type: If specified, only include this image type
            latest_lts_count: If specified, only include the N latest LTS versions

        Returns:
            Dictionary with matrix configuration for GitHub Actions
        """
        summary_path = self.data_dir / "build_summary.json"
        if not summary_path.exists():
            self.logger.error(f"Build summary not found at {summary_path}. Run build first.")
            return {"include": []}

        with summary_path.open() as f:
            build_summary = json.load(f)

        matrix_entries = []

        # Process runtime-specific images (python, python-gpu)
        for runtime_key, runtime_data in build_summary["build_details"].items():
            # Skip non-runtime-specific builds
            if runtime_key == "non_runtime_specific":
                continue

            # Extract runtime version and ML flag
            is_ml = runtime_key.endswith("_ml")
            runtime = runtime_key.replace("_ml", "")

            # Filter by LTS if requested
            if only_lts and "LTS" not in runtime:
                continue

            # Process each image type for this runtime
            for img_type, files in runtime_data.items():
                # Filter by image type if requested
                if image_type and img_type != image_type:
                    continue

                # Only process runtime-specific images
                # Non-runtime-specific: minimal, minimal-gpu, standard, standard-gpu, gpu
                # Runtime-specific: python, python-gpu
                if img_type not in ["python", "python-gpu"]:
                    continue

                if not files:
                    continue

                # Extract variation suffix from the first file path
                # e.g., "data/python/17.3-LTS-ubuntu2404-py312/Dockerfile"
                # We want to extract: "-ubuntu2404-py312"
                # The runtime dir includes: VERSION-LTS-SUFFIX or VERSION-SUFFIX
                first_file = files[0]
                parts = first_file.split("/")
                if len(parts) >= 3:
                    runtime_dir = parts[2]
                    # Extract suffix: everything after the runtime version
                    # Runtime version is stored in the 'runtime' variable (e.g., "17.3 LTS")
                    # Replace spaces with dashes to match the directory format
                    runtime_sanitized = runtime.replace(" ", "-")

                    # Remove the runtime prefix to get just the suffix
                    if runtime_dir.startswith(runtime_sanitized):
                        suffix = runtime_dir[len(runtime_sanitized) :]
                        # Remove -ml suffix if present (it's tracked separately)
                        suffix = suffix.replace("-ml", "")
                    else:
                        # Fallback: try to find the ubuntu/py pattern
                        import re

                        match = re.search(r"(-ubuntu\d+-py\d+)", runtime_dir)
                        suffix = match.group(1) if match else ""
                else:
                    suffix = ""

                # Create matrix entry
                entry = {
                    "runtime": runtime,
                    "image_type": img_type,
                    "variant": ".ml" if is_ml else "",
                    "suffix": suffix,
                }

                matrix_entries.append(entry)

        # Remove duplicates (multiple files for same runtime/image_type/variant combination)
        unique_entries = []
        seen = set()
        for entry in matrix_entries:
            key = (entry["runtime"], entry["image_type"], entry["variant"], entry["suffix"])
            if key not in seen:
                seen.add(key)
                unique_entries.append(entry)

        # Sort by runtime version (descending) and image type
        unique_entries.sort(
            key=lambda x: (
                not x["runtime"].startswith("17"),  # Most recent LTS first
                not x["runtime"].startswith("16"),
                not x["runtime"].startswith("15"),
                not x["runtime"].startswith("14"),
                x["runtime"],
                x["image_type"],
                x["variant"],
            )
        )

        # Apply latest LTS count filter if specified
        if latest_lts_count is not None:
            # Get unique runtime versions (sorted by most recent first)
            runtime_versions = []
            seen_versions = set()
            for entry in unique_entries:
                if entry["runtime"] not in seen_versions:
                    runtime_versions.append(entry["runtime"])
                    seen_versions.add(entry["runtime"])

            # Take only the latest N versions
            latest_versions = set(runtime_versions[:latest_lts_count])

            # Filter entries to only include latest versions
            unique_entries = [e for e in unique_entries if e["runtime"] in latest_versions]

        return {"include": unique_entries}

    def run(self, registry: str | None = None) -> dict[str, dict[str, list[Path]]]:
        """Main entry point to run the complete engine process.

        Args:
            registry: Optional registry prefix for image naming

        Returns:
            Dictionary mapping runtime versions to generated files
        """
        self.logger.info("Starting ContainerEngine run")
        result = self.build_all_images_for_all_runtimes(registry)
        self.logger.info("ContainerEngine run completed")
        return result
