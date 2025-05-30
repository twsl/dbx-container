import argparse
from pathlib import Path
import sys
from typing import Literal

from rich.console import Console
from rich.text import Text

from dbx_container.__about__ import __version__
from dbx_container.data.scraper import RuntimeScraper
from dbx_container.engine import RuntimeContainerEngine
from dbx_container.utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


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
        "--threads", type=int, default=5, help="Number of threads to use for runtime processing (default: 5)"
    )
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")
    parser.set_defaults(func=run_build_dockerfiles)


def run_build_dockerfiles(args) -> Literal[1] | Literal[0]:
    """Run the build dockerfiles command."""
    try:
        verify_ssl = not args.no_verify_ssl
        output_dir = Path(args.output_dir)

        console.print("[green]Building Dockerfiles...[/green]")
        console.print(f"Output directory: {output_dir}")

        # Initialize the container engine
        engine = RuntimeContainerEngine(data_dir=output_dir, max_workers=args.threads, verify_ssl=verify_ssl)

        if args.runtime_version:
            console.print(f"Building for specific runtime: {args.runtime_version}")
            # Get the specific runtime
            runtimes = engine.scraper.get_supported_runtimes()
            target_runtime = None
            for runtime in runtimes:
                if runtime.version == args.runtime_version:
                    target_runtime = runtime
                    break

            if not target_runtime:
                console.print(f"[red]Error: Runtime version '{args.runtime_version}' not found[/red]")
                return 1

            if args.image_type:
                # Build specific image type for specific runtime
                console.print(f"Building {args.image_type} image for runtime {args.runtime_version}")
                config = engine.image_types.get(args.image_type)
                if not config:
                    console.print(f"[red]Error: Unknown image type '{args.image_type}'[/red]")
                    return 1

                dockerfile_content = engine.generate_dockerfile_for_image_type(target_runtime, args.image_type, config)
                dockerfile_path = engine.save_dockerfile(dockerfile_content, target_runtime, args.image_type)
                metadata_path = engine.save_runtime_metadata(target_runtime, args.image_type)

                console.print(f"[green]✓[/green] Generated {args.image_type} Dockerfile: {dockerfile_path}")
                console.print(f"[green]✓[/green] Generated metadata: {metadata_path}")
            else:
                # Build all image types for specific runtime
                generated_files = engine.build_all_images_for_runtime(target_runtime)
                for image_type, files in generated_files.items():
                    if files:
                        console.print(f"[green]✓[/green] Generated {image_type} files: {len(files)} files")
                    else:
                        console.print(f"[yellow]⚠[/yellow] Failed to generate {image_type} files")
        else:
            # Build for all runtimes
            if args.image_type:
                console.print(f"Building {args.image_type} images for all runtimes")
                runtimes = engine.scraper.get_supported_runtimes()
                config = engine.image_types.get(args.image_type)
                if not config:
                    console.print(f"[red]Error: Unknown image type '{args.image_type}'[/red]")
                    return 1

                success_count = 0
                for runtime in runtimes:
                    try:
                        dockerfile_content = engine.generate_dockerfile_for_image_type(runtime, args.image_type, config)
                        engine.save_dockerfile(dockerfile_content, runtime, args.image_type)
                        engine.save_runtime_metadata(runtime, args.image_type)
                        success_count += 1
                        console.print(f"[green]✓[/green] Generated {args.image_type} for {runtime.version}")
                    except Exception as e:
                        console.print(f"[red]✗[/red] Failed {args.image_type} for {runtime.version}: {e}")

                console.print(f"[green]Completed: {success_count}/{len(runtimes)} runtimes[/green]")
            else:
                # Build all image types for all runtimes
                result = engine.run()
                total_runtimes = len(result)
                console.print(f"[green]✓[/green] Completed building for {total_runtimes} runtimes")

                # Display summary
                for runtime_key, runtime_files in result.items():
                    successful_images = sum(1 for files in runtime_files.values() if files)
                    total_images = len(runtime_files)
                    console.print(f"  {runtime_key}: {successful_images}/{total_images} image types")

        console.print("[green]Build completed successfully![/green]")

    except Exception as e:
        console.print(f"[red]Error during build: {e}[/red]")
        logger.exception("Build failed")
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
        console.print("Fetching Databricks runtime information...")
        fetcher = RuntimeScraper(max_workers=args.threads, verify_ssl=verify_ssl)
        fetcher.get_supported_runtimes()

    return display_runtimes(verify_ssl=verify_ssl)


def main() -> Literal[1] | Literal[0]:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description=f"dbx-container v{__version__}")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add commands
    setup_list_command(subparsers)
    setup_build_command(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # If no command is provided, show help
    if not args.command:
        text = Text(f"dbx-container v{__version__}", style="bold blue")
        console.print(text)
        console.print("\nAvailable commands:")
        console.print("  list   - List all available Databricks runtimes")
        console.print("  build  - Build Dockerfiles for Databricks runtimes")
        console.print("Use 'dbx-container <command> --help' for more information about a command.")
        return 0
    else:
        # Run the appropriate command
        if hasattr(args, "func"):
            return args.func(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
