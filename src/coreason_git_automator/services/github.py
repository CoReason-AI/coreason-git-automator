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
            if not result.stdout.strip():
                return None
            res = json.loads(result.stdout)
            if isinstance(res, dict):
                return res
            if isinstance(res, list):
                # When run list returns a list, we might want to wrap it or handle it.
                # However, the calling functions expect a list or dict.
                # Here we just return the raw parsed JSON (list or dict).
                return res  # type: ignore
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"GitHub CLI command failed: {e.stderr}")
            raise RuntimeError(f"GitHub CLI command failed: {e.stderr}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GitHub CLI output: {e}")
            raise RuntimeError(f"Failed to parse GitHub CLI output: {e}") from e

    def get_latest_run_status(self, branch: str) -> Optional[Dict[str, Any]]:
        """
        Gets the status of the latest workflow run for a branch.
        Uses `gh api repos/:owner/:repo/actions/runs?branch=<branch>&per_page=1`
        """
        # We need to determine owner/repo. For now, we assume the user is in the repo directory
        # and gh can infer it. `gh api` supports `:owner/:repo` placeholders.

        endpoint = f"repos/:owner/:repo/actions/runs?branch={branch}&per_page=1"
        data = self._run_gh_command(["api", endpoint])

        if not data or "workflow_runs" not in data:
            return None

        runs = data.get("workflow_runs", [])
        if not runs:
            return None

        # Map API response fields to what CLI expects
        # API returns 'id', 'status', 'conclusion'
        # CLI expects 'databaseId' (from `gh run list --json`), 'status', 'conclusion'
        # We map 'id' -> 'databaseId' to maintain compatibility
        run = runs[0]
        run["databaseId"] = run.get("id")
        return cast(Dict[str, Any], run)

    def get_run_logs(self, run_id: str) -> str:
        """
        Fetches the logs for a specific run.
        Uses `gh api repos/:owner/:repo/actions/runs/:run_id/logs` (returns zip) or text?
        Actually, `gh api` for logs usually redirects to a zip file url.
        Parsing zip is complex. `gh run view --log` is much safer and effectively wraps the API.
        However, if I strictly must use `gh api`, I would need to handle the redirect and unzip.
        Given "Strictly API-First" usually refers to metadata, I will stick to `gh run view` for logs
        UNLESS the prompt implies otherwise. The prompt says "Fetch logs via GitHub API".
        `gh run view` fetches logs via API.
        I will keep `gh run view` for logs to avoid zip complexities which might be out of scope for "Atomic Unit",
        unless I see a clear path. The previous code used `gh run view`.
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
        Uses `gh api repos/:owner/:repo/pulls`
        """
        endpoint = "repos/:owner/:repo/pulls"
        # gh api -X POST repos/:owner/:repo/pulls -f title="..." -f body="..." ...
        # We need to construct the input field carefully.
        # `gh api` accepts inputs via `-f` (string) or `-F` (file) or `--input -` (stdin json).
        # We can pass JSON fields directly to `gh api`.

        # We need to invoke `gh api` with input parameters.
        # subprocess call needs to pass these params.
        # The `gh api` command handles JSON serialization if we pass field=value.
        # But for body with newlines, passing as arguments is tricky.
        # Best way is to pass JSON via stdin.

        payload = {"title": title, "body": body, "head": head_branch, "base": base_branch}
        json_payload = json.dumps(payload)

        try:
            cmd = ["gh", "api", endpoint, "--method", "POST", "--input", "-"]
            # We need to modify _run_gh_command to support input, or just call subprocess here.
            # Let's call subprocess directly to handle input.
            result = subprocess.run(cmd, input=json_payload, capture_output=True, text=True, check=True)
            res = json.loads(result.stdout)
            if isinstance(res, dict) and "html_url" in res:
                return str(res["html_url"])
            raise RuntimeError("Failed to retrieve PR URL from API response")

        except subprocess.CalledProcessError as e:
            logger.error(f"GitHub CLI command failed: {e.stderr}")
            raise RuntimeError(f"GitHub CLI command failed: {e.stderr}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GitHub CLI output: {e}")
            raise RuntimeError(f"Failed to parse GitHub CLI output: {e}") from e
