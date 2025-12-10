import argparse
from pathlib import Path
import sys
from typing import Literal

from rich.panel import Panel
from rich.text import Text

from dbx_container.__about__ import __version__
from dbx_container.data.scraper import RuntimeScraper
from dbx_container.engine import RuntimeContainerEngine
from dbx_container.utils.logging import get_logger

logger = get_logger(__name__)


def display_runtimes(runtimes: list | None = None, verify_ssl: bool = True) -> Literal[1] | Literal[0]:
    """Display runtime information in a rich table."""
    # Create a fetcher to load or fetch runtimes
    fetcher = RuntimeScraper(verify_ssl=verify_ssl)

    result = fetcher.display_runtimes()
    return 0 if result else 1


def setup_build_command(subparsers) -> None:
    """Setup the build dockerfiles command."""
    parser = subparsers.add_parser("build", help="Build Dockerfiles for Databricks runtimes")
    parser.add_argument(
        "--output-dir", type=str, default="data", help="Output directory for generated Dockerfiles (default: data)"
    )
    parser.add_argument(
        "--runtime-version",
        type=str,
        help="Specific runtime version to build (e.g., '14.3.x-scala2.12'). If not provided, builds for all runtimes",
    )
    parser.add_argument(
        "--image-type",
        type=str,
        choices=["minimal", "python", "dbfsfuse", "standard", "gpu"],
        help="Specific image type to build. If not provided, builds all image types",
    )
    parser.add_argument(
        "--registry",
        type=str,
        help="Registry prefix for image naming (e.g., 'ghcr.io/owner' or 'docker.io/username'). If not provided, uses local tags",
    )
    parser.add_argument(
        "--threads", type=int, default=5, help="Number of threads to use for runtime processing (default: 5)"
    )
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument(
        "--latest-lts-only",
        action="store_true",
        help="Build only the latest 3 LTS versions (default behavior)",
    )
    parser.add_argument(
        "--all-lts",
        action="store_true",
        help="Build all LTS versions (overrides --latest-lts-only)",
    )
    parser.add_argument(
        "--lts-count",
        type=int,
        default=3,
        help="Number of latest LTS versions to build when --latest-lts-only is used (default: 3)",
    )
    parser.set_defaults(func=run_build_dockerfiles)


def run_build_dockerfiles(args) -> Literal[1] | Literal[0]:
    """Run the build dockerfiles command."""
    try:
        verify_ssl = not args.no_verify_ssl
        output_dir = Path(args.output_dir)

        # Show header
        logger.print(
            Panel(
                f"[bold green]🔨 Building Dockerfiles[/bold green]\nOutput directory: [cyan]{output_dir}[/cyan]",
                expand=False,
                border_style="green",
            )
        )

        # Determine LTS filtering
        lts_count = None if args.all_lts else args.lts_count
        if not args.runtime_version and not args.all_lts:
            logger.info(f"Building latest {args.lts_count} LTS versions only (use --all-lts for all LTS versions)")

        # Initialize the container engine
        engine = RuntimeContainerEngine(
            data_dir=output_dir,
            max_workers=args.threads,
            verify_ssl=verify_ssl,
            latest_lts_count=lts_count,
        )

        if args.runtime_version:
            logger.info(f"Building for specific runtime: {args.runtime_version}")
            # Get the specific runtime
            with logger.status("[bold green]Fetching runtime information..."):
                runtimes = engine.scraper.get_supported_runtimes()

            target_runtime = None
            for runtime in runtimes:
                if runtime.version == args.runtime_version:
                    target_runtime = runtime
                    break

            if not target_runtime:
                logger.error(f"Runtime version '{args.runtime_version}' not found")
                return 1

            if args.image_type:
                # Build specific image type for specific runtime
                logger.info(f"Building {args.image_type} image for runtime {args.runtime_version}")
                config = engine.image_types.get(args.image_type)
                if not config:
                    logger.error(f"Unknown image type '{args.image_type}'")
                    return 1

                with logger.status(f"[bold green]Generating {args.image_type} image..."):
                    dockerfile_content = engine.generate_dockerfile_for_image_type(
                        target_runtime, args.image_type, config, registry=args.registry
                    )
                    dockerfile_path = engine.save_dockerfile(dockerfile_content, target_runtime, args.image_type)
                    metadata_path = engine.save_runtime_metadata(target_runtime, args.image_type)

                logger.info(f"Generated {args.image_type} Dockerfile: {dockerfile_path}")
                logger.info(f"Generated metadata: {metadata_path}")
            else:
                # Build all image types for specific runtime
                generated_files = engine.build_all_images_for_runtime(target_runtime, args.registry)
                success_count = sum(1 for files in generated_files.values() if files)
                logger.info(f"Generated {success_count}/{len(generated_files)} image types successfully")
        else:
            # Build for all runtimes
            if args.image_type:
                logger.info(f"Building {args.image_type} images for all runtimes")

                with logger.status("[bold green]Fetching runtime information..."):
                    runtimes = engine.scraper.get_supported_runtimes()

                config = engine.image_types.get(args.image_type)
                if not config:
                    logger.error(f"Unknown image type '{args.image_type}'")
                    return 1

                success_count = 0
                for runtime in logger.progress(runtimes, description=f"Building {args.image_type} images"):
                    try:
                        dockerfile_content = engine.generate_dockerfile_for_image_type(
                            runtime, args.image_type, config, registry=args.registry
                        )
                        engine.save_dockerfile(dockerfile_content, runtime, args.image_type)
                        engine.save_runtime_metadata(runtime, args.image_type)
                        success_count += 1
                    except Exception:
                        logger.exception(f"Failed {args.image_type} for {runtime.version}")

                logger.info(f"Completed: {success_count}/{len(runtimes)} runtimes")
            else:
                # Build all image types for all runtimes
                result = engine.run(args.registry)
                total_runtimes = len(result)

                # Display summary
                successful_runtimes = sum(
                    1 for runtime_files in result.values() if any(files for files in runtime_files.values())
                )
                logger.info(f"Completed building for {successful_runtimes}/{total_runtimes} runtimes")

        logger.info("Build completed successfully!")

    except Exception:
        logger.exception("Error during build")
        return 1
    else:
        return 0


def setup_list_command(subparsers) -> None:
    """Setup the list runtimes command."""
    parser = subparsers.add_parser("list", help="List all available Databricks runtimes")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")
    parser.add_argument(
        "--threads", type=int, default=5, help="Number of threads to use for fetching runtime data (default: 5)"
    )
    parser.add_argument(
        "--fetch", action="store_true", help="Force fetching runtime information even if already available"
    )
    parser.set_defaults(func=run_list_runtimes)


def run_list_runtimes(args) -> Literal[1] | Literal[0]:
    """Run the list runtimes command."""
    verify_ssl = not args.no_verify_ssl

    # Force fetch if requested
    if args.fetch:
        logger.print(
            Panel(
                "[bold blue]📋 Fetching Databricks Runtime Information[/bold blue]", expand=False, border_style="blue"
            )
        )

        with logger.status("[bold blue]Fetching runtime information..."):
            fetcher = RuntimeScraper(max_workers=args.threads, verify_ssl=verify_ssl)
            fetcher.get_supported_runtimes()

    return display_runtimes(verify_ssl=verify_ssl)


def setup_generate_matrix_command(subparsers) -> None:
    """Setup the generate matrix command."""
    parser = subparsers.add_parser("generate-matrix", help="Generate GitHub Actions build matrix from build summary")
    parser.add_argument(
        "--output-dir", type=str, default="data", help="Directory containing build_summary.json (default: data)"
    )
    parser.add_argument(
        "--only-lts",
        action="store_true",
        help="Only include LTS runtimes in the matrix",
    )
    parser.add_argument(
        "--image-type",
        type=str,
        choices=["gpu"],
        help="Specific image type to include in matrix (currently only 'gpu' is runtime-specific)",
    )
    parser.add_argument(
        "--latest-lts-count",
        type=int,
        help="Only include the N latest LTS versions in the matrix",
    )
    parser.set_defaults(func=run_generate_matrix)


def run_generate_matrix(args) -> Literal[1] | Literal[0]:
    """Run the generate matrix command."""
    import json

    try:
        output_dir = Path(args.output_dir)

        # Initialize the container engine (we just need it for the method)
        engine = RuntimeContainerEngine(data_dir=output_dir)

        # Generate the matrix
        matrix = engine.generate_build_matrix(
            only_lts=args.only_lts,
            image_type=args.image_type,
            latest_lts_count=args.latest_lts_count,
        )

        # Output as JSON for GitHub Actions
        print(json.dumps(matrix))
    except Exception:
        logger.exception("Error generating matrix")
        return 1
    else:
        return 0


def main() -> Literal[1] | Literal[0]:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description=f"dbx-container v{__version__}")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add commands
    setup_list_command(subparsers)
    setup_build_command(subparsers)
    setup_generate_matrix_command(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # If no command is provided, show help
    if not args.command:
        text = Text(f"dbx-container v{__version__}", style="bold blue")
        logger.print(text)
        logger.print("\nAvailable commands:")
        logger.print("  list            - List all available Databricks runtimes")
        logger.print("  build           - Build Dockerfiles for Databricks runtimes")
        logger.print("  generate-matrix - Generate GitHub Actions build matrix")
        logger.print("Use 'dbx-container <command> --help' for more information about a command.")
        return 0
    else:
        # Run the appropriate command
        if hasattr(args, "func"):
            return args.func(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
