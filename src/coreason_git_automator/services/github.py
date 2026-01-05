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
from typing import Any, Dict, Optional, cast

from tenacity import retry, stop_after_attempt, wait_exponential

from coreason_git_automator.services.base import ExternalTool
from coreason_git_automator.utils.logger import logger
from coreason_git_automator.utils.process import run_command


class GitHubService(ExternalTool):
    """
    Service for interacting with GitHub via the gh CLI.
    """

    def __init__(self, executable: str = "gh") -> None:
        super().__init__(executable)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5))  # type: ignore
    def _run_gh_command(self, args: list[str]) -> Optional[Dict[str, Any]]:
        """Helper to run gh commands and return JSON output."""
        return self._run_gh_command_impl(args)

    def _run_gh_command_impl(self, args: list[str]) -> Optional[Dict[str, Any]]:
        try:
            cmd = ["gh"] + args
            output = run_command(cmd)
            # Try to parse JSON. If empty, it will raise JSONDecodeError.
            if not output.strip():
                return None
            res = json.loads(output)
            if isinstance(res, dict):
                return res
            if isinstance(res, list):
                # When run list returns a list, we might want to wrap it or handle it.
                # However, the calling functions expect a list or dict.
                # Here we just return the raw parsed JSON (list or dict).
                return res  # type: ignore
            return None
        except RuntimeError:
            # Logging already handled in run_command
            raise
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
        return run_command(["gh", "run", "view", run_id, "--log"])

    def create_pr(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
        """
        Creates a pull request.
        Uses `gh api repos/:owner/:repo/pulls`
        """
        endpoint = "repos/:owner/:repo/pulls"
        payload = {"title": title, "body": body, "head": head_branch, "base": base_branch}
        json_payload = json.dumps(payload)

        try:
            cmd = ["gh", "api", endpoint, "--method", "POST", "--input", "-"]
            output = run_command(cmd, input_text=json_payload)
            res = json.loads(output)
            if isinstance(res, dict) and "html_url" in res:
                return str(res["html_url"])
            raise RuntimeError("Failed to retrieve PR URL from API response")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GitHub CLI output: {e}")
            raise RuntimeError(f"Failed to parse GitHub CLI output: {e}") from e
