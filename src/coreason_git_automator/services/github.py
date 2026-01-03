# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import json
import shutil
import subprocess
from typing import Any, Dict, Optional, cast

from tenacity import retry, stop_after_attempt, wait_exponential

from coreason_git_automator.utils.logger import logger


class GitHubService:
    """
    Service for interacting with GitHub via the gh CLI.
    """

    def __init__(self, executable: str = "gh"):
        self.executable = executable

    def verify_installed(self) -> str:
        """Verifies gh CLI is installed and returns version."""
        if not shutil.which(self.executable):
            raise RuntimeError(f"GitHub CLI '{self.executable}' not found in PATH.")

        try:
            result = subprocess.run([self.executable, "--version"], capture_output=True, text=True, check=True)
            return str(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check GitHub CLI version: {e.stderr}")
            raise RuntimeError(f"Failed to check GitHub CLI version: {e.stderr}") from e

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5))  # type: ignore
    def _run_gh_command(self, args: list[str]) -> Optional[Dict[str, Any]]:
        """Helper to run gh commands and return JSON output."""
        return self._run_gh_command_impl(args)

    def _run_gh_command_impl(self, args: list[str]) -> Optional[Dict[str, Any]]:
        try:
            cmd = ["gh"] + args
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # Try to parse JSON. If empty, it will raise JSONDecodeError.
            res = json.loads(result.stdout)
            if isinstance(res, dict):
                return res
            if isinstance(res, list):
                return res  # type: ignore
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"GitHub CLI command failed: {e.stderr}")
            raise RuntimeError(f"GitHub CLI command failed: {e.stderr}") from e
        except json.JSONDecodeError as e:
            # If output is empty, return None (no result). Otherwise re-raise.
            if not result.stdout.strip():  # pragma: no cover
                return None
            logger.error(f"Failed to parse GitHub CLI output: {e}")
            raise RuntimeError(f"Failed to parse GitHub CLI output: {e}") from e

    def get_latest_run_status(self, branch: str) -> Optional[Dict[str, Any]]:
        """
        Gets the status of the latest workflow run for a branch.
        """
        # gh run list --branch <branch> --limit 1 --json status,conclusion,databaseId
        data = self._run_gh_command(
            ["run", "list", "--branch", branch, "--limit", "1", "--json", "status,conclusion,databaseId"]
        )

        if not data or not isinstance(data, list) or len(data) == 0:
            return None

        return cast(Dict[str, Any], data[0])

    def get_run_logs(self, run_id: str) -> str:
        """
        Fetches the logs for a specific run.
        Uses `gh run view <run_id> --log`.
        """
        try:
            cmd = ["gh", "run", "view", run_id, "--log"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to fetch logs: {e.stderr}")
            raise RuntimeError(f"Failed to fetch logs: {e.stderr}") from e

    def create_pr(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
        """
        Creates a pull request.
        """
        # gh pr create --title <title> --body <body> --head <head> --base <base> --json url
        data = self._run_gh_command(
            [
                "pr",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--head",
                head_branch,
                "--base",
                base_branch,
                "--json",
                "url",
            ]
        )

        if isinstance(data, dict) and "url" in data:
            return str(data["url"])
        raise RuntimeError("Failed to retrieve PR URL")
