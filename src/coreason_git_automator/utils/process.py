# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import subprocess
from typing import List, Optional

from coreason_git_automator.utils.logger import logger


def run_command(
    cmd: List[str], check: bool = True, input_text: Optional[str] = None, capture_output: bool = True
) -> str:
    """
    Executes a subprocess command safely with logging and error handling.

    Args:
        cmd: List of command arguments.
        check: Whether to raise an exception on non-zero exit code.
        input_text: Input string to pass to stdin.
        capture_output: Whether to capture stdout/stderr.

    Returns:
        The stdout output as a string (if captured).

    Raises:
        RuntimeError: If the command fails and check is True.
    """
    try:
        # logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=capture_output,
            encoding="utf-8",
            errors="replace",
            check=check,
        )
        return result.stdout.strip() if result.stdout else ""
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed: {' '.join(cmd)}\nStderr: {e.stderr}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
