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
from pathlib import Path
from typing import List, Optional

from coreason_git_automator.utils.logger import logger
from coreason_git_automator.utils.process import run_command


class JulesWrapper:
    """
    Wrapper around the Jules CLI.
    """

    def __init__(self, executable: str = "jules"):
        found = shutil.which(executable)
        if not found:
            raise RuntimeError(f"Jules executable '{executable}' not found in PATH.")
        self.executable: str = found

    def verify_version(self) -> str:
        """Verifies Jules is installed and returns version."""
        try:
            return run_command([self.executable, "--version"])
        except RuntimeError as e:
            logger.error(f"Failed to check Jules version: {e}")
            raise

    def _prepare_prompt(self, prompt: str, context_files: Optional[List[Path]]) -> str:
        """Prepends context files to the prompt."""
        if not context_files:
            return prompt

        context_str = ""
        for file_path in context_files:
            try:
                content = file_path.read_text(encoding="utf-8")
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
            run_command([self.executable, "remote", "new", full_prompt])
        except RuntimeError as e:
            logger.error(f"Jules session failed: {e}")
            raise

    def send_feedback(self, errors: str) -> None:
        """Sends feedback (errors) to the active Jules session."""
        msg = f"Fix the code based on these errors:\n\n{errors}"
        try:
            run_command([self.executable, "remote", "chat", msg])
        except RuntimeError as e:
            logger.error(f"Failed to send feedback to Jules: {e}")
            raise
