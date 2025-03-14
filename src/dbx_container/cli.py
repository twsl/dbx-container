import argparse
import sys
from typing import Literal

from rich.console import Console
from rich.text import Text

from dbx_container.__about__ import __version__
from dbx_container.data.scraper import RuntimeScraper
from dbx_container.utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


def display_runtimes(runtimes: list | None = None, verify_ssl: bool = True) -> Literal[1] | Literal[0]:
    """Display runtime information in a rich table."""
    # Create a fetcher to load or fetch runtimes
    fetcher = RuntimeScraper(verify_ssl=verify_ssl)

    result = fetcher.display_runtimes()
    return 0 if result else 1


def setup_list_command(subparsers) -> None:
    """Setup the list runtimes command."""
    parser = subparsers.add_parser("list", help="List all available Databricks runtimes")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")
    parser.set_defaults(func=run_list_runtimes)


def run_list_runtimes(args) -> Literal[1] | Literal[0]:
    """Run the list runtimes command."""
    verify_ssl = not args.no_verify_ssl
    return display_runtimes(verify_ssl=verify_ssl)


def main() -> Literal[1] | Literal[0]:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description=f"dbx-container v{__version__}")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--threads", type=int, default=5, help="Number of threads to use for fetching runtime data (default: 5)"
    )
    parser.add_argument(
        "--fetch", action="store_true", help="Force fetching runtime information even if already available"
    )
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification")

    subparsers = parser.add_subparsers(dest="command", help="Command to run (optional)")

    # Add commands
    setup_list_command(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # If no command is provided, automatically show version info and available runtimes
    if not args.command:
        text = Text(f"dbx-container v{__version__}", style="bold blue")
        console.print(text)

        verify_ssl = not args.no_verify_ssl
        if not verify_ssl:
            console.print("[yellow]SSL certificate verification is disabled[/yellow]")

        # Force fetch if requested
        if args.fetch:
            console.print("Fetching Databricks runtime information...")
            fetcher = RuntimeScraper(max_workers=args.threads, verify_ssl=verify_ssl)
            fetcher.get_supported_runtimes()

        # Display runtimes
        return display_runtimes(verify_ssl=verify_ssl)
    else:
        # Run the appropriate command
        if hasattr(args, "func"):
            return args.func(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
