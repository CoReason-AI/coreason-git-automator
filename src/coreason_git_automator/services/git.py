# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from typing import List

from coreason_git_automator.utils.process import run_command


class GitClient:
    """
    Client for local git operations.
    """

    def run(self, args: List[str]) -> str:
        """Runs a git command."""
        # Wrap the generic RuntimeError from run_command if needed, or just let it bubble up.
        # The original implementation raised RuntimeError with "Git command failed: ...".
        # run_command raises RuntimeError with "Command failed: ...".
        # Close enough, but strictly speaking "Git command failed" vs "Command failed".
        # Let's trust run_command's logging.
        return run_command(["git"] + args)

    def get_log_oneline(self, branch: str) -> str:
        return self.run(["log", "--oneline", branch])

    def checkout(self, branch: str) -> None:
        self.run(["checkout", branch])

    def pull(self) -> None:
        self.run(["pull"])

    def create_branch(self, branch: str) -> None:
        self.run(["checkout", "-b", branch])

    def merge_squash(self, branch: str) -> None:
        self.run(["merge", "--squash", branch])

    def commit(self, title: str, body: str) -> None:
        message = f"{title}\n\n{body}"
        self.run(["commit", "-m", message])

    def push(self, branch: str) -> None:
        self.run(["push", "-u", "origin", branch])
