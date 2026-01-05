# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import shutil
from typing import Optional

from coreason_git_automator.utils.logger import logger
from coreason_git_automator.utils.process import run_command


class ExternalTool:
    """
    Base class for services that wrap an external CLI executable.
    """

    def __init__(self, executable: str) -> None:
        self._path: Optional[str] = shutil.which(executable)
        if not self._path:
            raise RuntimeError(f"Executable '{executable}' not found in PATH.")
        self.executable = self._path

    def verify_installed(self) -> str:
        """
        Verifies the tool is installed and returns its version.
        Assumes the tool supports a `--version` flag.
        """
        try:
            return run_command([self.executable, "--version"])
        except RuntimeError as e:
            logger.error(f"Failed to check version for {self.executable}: {e}")
            raise
