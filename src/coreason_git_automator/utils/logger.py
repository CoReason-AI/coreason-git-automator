# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from pathlib import Path

from loguru import logger
from rich.logging import RichHandler

__all__ = ["logger", "configure_logging"]


def configure_logging() -> None:
    """
    Configures logging with RichHandler for console and rotating file for audit trail.
    Adheres to Unified Observability Layer specs:
    - Console: RichHandler (INFO)
    - File: logs/app.log (DEBUG, JSON, Rotated 500 MB, Retained 10 days)
    """
    logger.remove()

    # Sink 1: Console via Rich (INFO level, visual integration)
    logger.add(
        RichHandler(rich_tracebacks=True, markup=True),
        level="INFO",
        format="{message}",  # RichHandler handles timestamp/level styling
    )

    # Sink 2: Audit Trail File (DEBUG level, rotating, JSON)
    # Log to logs/app.log
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    logger.add(
        str(log_file),
        rotation="500 MB",
        retention="10 days",
        level="DEBUG",
        enqueue=True,  # Thread-safe
        backtrace=True,
        diagnose=True,
        serialize=True,  # JSON format
        encoding="utf-8",
    )
