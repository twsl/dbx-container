from collections.abc import Iterable
import logging
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.status import Status

# Global console instance shared across all loggers
_console = Console()

# Global registry to track created loggers and prevent duplicates
_logger_registry = {}


class RichLogger(logging.Logger):
    """A rich-enhanced logger that inherits from logging.Logger."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.console = _console
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Setup the logger with Rich handler."""
        self.setLevel(logging.INFO)

        # Prevent propagation to root logger to avoid duplicate output
        self.propagate = False

        # Remove existing handlers to avoid duplication
        for handler in self.handlers[:]:
            self.removeHandler(handler)

        # Add Rich handler
        rich_handler = RichHandler(
            console=self.console, show_time=False, show_path=False, rich_tracebacks=True, markup=True
        )
        rich_handler.setLevel(logging.INFO)
        self.addHandler(rich_handler)

    def info(self, msg, *args, **kwargs) -> None:
        """Log info message with rich formatting."""
        message = msg % args if args else str(msg)
        # Merge extra parameter properly
        extra = kwargs.pop("extra", {})
        extra["markup"] = True
        super().info(f"[green]✓[/green] {message}", extra=extra, **kwargs)

    def error(self, msg, *args, **kwargs) -> None:
        """Log error message with rich formatting."""
        message = msg % args if args else str(msg)
        # Merge extra parameter properly
        extra = kwargs.pop("extra", {})
        extra["markup"] = True
        super().error(f"[red]✗[/red] {message}", extra=extra, **kwargs)

    def warning(self, msg, *args, **kwargs) -> None:
        """Log warning message with rich formatting."""
        message = msg % args if args else str(msg)
        # Merge extra parameter properly
        extra = kwargs.pop("extra", {})
        extra["markup"] = True
        super().warning(f"[yellow]⚠[/yellow] {message}", extra=extra, **kwargs)

    def debug(self, msg, *args, **kwargs) -> None:
        """Log debug message with rich formatting."""
        message = msg % args if args else str(msg)
        # Merge extra parameter properly
        extra = kwargs.pop("extra", {})
        extra["markup"] = True
        super().debug(f"[dim]•[/dim] {message}", extra=extra, **kwargs)

    def exception(self, msg, *args, **kwargs) -> None:
        """Log exception with rich formatting."""
        message = msg % args if args else str(msg)
        # Merge extra parameter properly
        extra = kwargs.pop("extra", {})
        extra["markup"] = True
        super().exception(f"[red]💥[/red] {message}", extra=extra, **kwargs)

    def print(self, *args, **kwargs) -> None:
        """Print directly to console with rich formatting."""
        self.console.print(*args, **kwargs)

    def status(self, *args, **kwargs) -> Status:
        """Create a status context manager."""
        return self.console.status(*args, **kwargs)

    def progress(self, *args, **kwargs) -> Iterable[Any]:
        """Create a progress context manager."""
        from rich.progress import track

        # Check if there's already a live display active and use a simpler approach
        try:
            return track(*args, console=self.console, **kwargs)
        except Exception:
            # If there's a LiveError or other issue, fall back to simple iteration
            # with periodic logging
            sequence = args[0] if args else []
            description = kwargs.get("description", "Processing")
            total = len(sequence) if hasattr(sequence, "__len__") else None

            # Log start
            if total:
                self.info(f"{description} - {total} items to process")
            else:
                self.info(f"{description}")

            # Simple iteration with periodic updates
            for i, item in enumerate(sequence):
                if total and (i + 1) % max(1, total // 10) == 0:
                    self.info(f"Progress: {i + 1}/{total}")
                yield item

            # Log completion
            if total:
                self.info(f"Completed processing {total} items")
            else:
                self.info("Processing completed")

    def create_progress_bar(self, description: str = "Processing...") -> Progress:
        """Create a rich progress bar with standard configuration."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=_console,
            transient=True,  # Progress bar disappears when complete
        )


def get_logger(name: str) -> RichLogger:
    """Get a rich-enhanced logger instance."""
    # Check if we already have this logger in our registry
    if name in _logger_registry:
        return _logger_registry[name]

    # Check if logger already exists in the logging manager
    if name in logging.Logger.manager.loggerDict:
        existing_logger = logging.getLogger(name)

        # If it's already a RichLogger, register and return it
        if isinstance(existing_logger, RichLogger):
            _logger_registry[name] = existing_logger
            return existing_logger

        # If it's a regular logger, we need to replace it
        # Remove from the manager and create a fresh one
        del logging.Logger.manager.loggerDict[name]

    # Create a new RichLogger
    logging.setLoggerClass(RichLogger)
    logger = logging.getLogger(name)
    logging.setLoggerClass(logging.Logger)

    # Register the logger to prevent future duplicates
    _logger_registry[name] = logger

    return logger  # type: ignore[return-value]
