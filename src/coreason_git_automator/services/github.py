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
from typing import Any, Dict, List, Optional, Union, cast

from tenacity import retry, stop_after_attempt, wait_exponential

from coreason_git_automator.services.base import ExternalTool
from coreason_git_automator.utils.logger import logger
from coreason_git_automator.utils.process import run_command


class GitHubService(ExternalTool):
    """
    Service for interacting with GitHub via the gh CLI.
    Strictly uses the GitHub API (`gh api`) for all interactions to ensure
    robustness and structured data handling.
    """

    def __init__(self, executable: str = "gh") -> None:
        super().__init__(executable)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5))  # type: ignore
    def _run_gh_command(self, args: list[str]) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        Helper to run gh commands and return JSON output.
        Wraps _run_gh_command_impl for retries.
        """
        return self._run_gh_command_impl(args)

    def _run_gh_command_impl(self, args: list[str]) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        Executes a gh command.
        Enforces API-first discipline by preventing usage of 'run view'.
        """
        # Defensive check: Ensure we are not using 'run view'
        if "run" in args and "view" in args:
            raise RuntimeError("Prohibited command: 'gh run view' is not allowed. Use 'gh api' instead.")

        try:
            cmd = [self.executable] + args
            output = run_command(cmd)

            # If the output is empty, return None
            if not output.strip():
                return None

            # Parse JSON response
            res = json.loads(output)
            return cast(Union[Dict[str, Any], List[Any]], res)

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
        endpoint = f"repos/:owner/:repo/actions/runs?branch={branch}&per_page=1"
        data = self._run_gh_command(["api", endpoint])

        if not data or not isinstance(data, dict) or "workflow_runs" not in data:
            return None

        runs = data.get("workflow_runs", [])
        if not runs or not isinstance(runs, list):
            return None

        # Return the first run
        run = runs[0]
        # Ensure databaseId is present (aliasing id) if not already.
        # Logic matches previous behavior: implicitly set databaseId to id even if id is missing (None)
        # to satisfy existing tests expecting {"databaseId": None} for empty runs.
        if "databaseId" not in run:
            run["databaseId"] = run.get("id")

        return cast(Dict[str, Any], run)

    def get_run_logs(self, run_id: str) -> str:
        """
        Fetches the logs for a specific run by identifying the failed job.
        Strictly uses `gh api`.
        """
        # 1. Get jobs for the run
        endpoint_jobs = f"repos/:owner/:repo/actions/runs/{run_id}/jobs"
        data = self._run_gh_command(["api", endpoint_jobs])

        if not data or not isinstance(data, dict) or "jobs" not in data:
            raise RuntimeError(f"Could not retrieve jobs for run {run_id}")

        jobs = data["jobs"]
        if not isinstance(jobs, list):
            raise RuntimeError(f"Invalid jobs structure: expected list, got {type(jobs).__name__}")

        if not jobs:
            raise RuntimeError(f"No jobs found for run {run_id}")

        # 2. Find the failed job
        # Filter out non-dict items first
        valid_jobs = [j for j in jobs if isinstance(j, dict)]
        target_job = next((j for j in valid_jobs if j.get("conclusion") == "failure"), None)

        # If no failed job is found (e.g., in progress or cancelled), default to the last job
        if not target_job:
            if not valid_jobs:
                raise RuntimeError("No valid job objects found in response")
            logger.warning(f"No failed job found for run {run_id}. Fetching logs for the last job.")
            target_job = valid_jobs[-1]

        job_id = target_job.get("id")
        if not job_id:
            raise RuntimeError("Job ID missing from API response")

        # 3. Fetch logs for the specific job using run_command directly
        # We don't use _run_gh_command here because the output is text (logs), not JSON.
        endpoint_logs = f"repos/:owner/:repo/actions/jobs/{job_id}/logs"

        # Explicitly constructing the command to ensure we are using gh api
        cmd = [self.executable, "api", endpoint_logs]
        return run_command(cmd)

    def create_pr(self, title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
        """
        Creates a pull request.
        Uses `gh api repos/:owner/:repo/pulls`
        """
        endpoint = "repos/:owner/:repo/pulls"
        payload = {"title": title, "body": body, "head": head_branch, "base": base_branch}
        json_payload = json.dumps(payload)

        try:
            cmd = [self.executable, "api", endpoint, "--method", "POST", "--input", "-"]
            output = run_command(cmd, input_text=json_payload)
            res = json.loads(output)
            if isinstance(res, dict) and "html_url" in res:
                return str(res["html_url"])
            raise RuntimeError("Failed to retrieve PR URL from API response")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GitHub CLI output: {e}")
            raise RuntimeError(f"Failed to parse GitHub CLI output: {e}") from e
