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
import subprocess
from pathlib import Path
from typing import List, Optional

from coreason_git_automator.utils.logger import logger

class JulesWrapper:
    """
    Wrapper around the Jules CLI.
    """

    def __init__(self, executable: str = "jules"):
        self.executable = shutil.which(executable)
        if not self.executable:
            raise RuntimeError(f"Jules executable '{executable}' not found in PATH.")

    def verify_version(self) -> str:
        """Verifies Jules is installed and returns version."""
        try:
            result = subprocess.run(
                [self.executable, "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check Jules version: {e.stderr}")
            raise RuntimeError(f"Failed to check Jules version: {e.stderr}") from e

    def _prepare_prompt(self, prompt: str, context_files: Optional[List[Path]]) -> str:
        """Prepends context files to the prompt."""
        if not context_files:
            return prompt

        context_str = ""
        for file_path in context_files:
            try:
                content = file_path.read_text()
                context_str += f"[CONTEXT: {file_path}]\n{content}\n\n"
            except Exception as e:
                logger.warning(f"Failed to read context file {file_path}: {e}")

        return f"{context_str}[INSTRUCTION]\n{prompt}"

    def run_session(self, prompt: str, context_files: Optional[List[Path]] = None) -> None:
        """Starts a Jules session with the given prompt and context."""
        full_prompt = self._prepare_prompt(prompt, context_files)

        try:
            # According to spec: "Session Start: Use subprocess to call jules remote new."
            logger.info("Starting Jules session...")
            subprocess.run(
                [self.executable, "remote", "new", full_prompt],
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Jules session failed: {e}")
            raise RuntimeError(f"Jules session failed: {e}") from e

    def send_feedback(self, errors: str) -> None:
        """Sends feedback (errors) to the active Jules session."""
        msg = f"Fix the code based on these errors:\n\n{errors}"
        try:
            subprocess.run(
                [self.executable, "remote", "chat", msg],
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send feedback to Jules: {e}")
            raise RuntimeError(f"Failed to send feedback to Jules: {e}") from e
