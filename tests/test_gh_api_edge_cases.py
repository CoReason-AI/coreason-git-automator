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
from unittest.mock import MagicMock, patch

import pytest
from tenacity import RetryError

from coreason_git_automator.services.github import GitHubService


@pytest.fixture
def github_service():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        return GitHubService()


def test_workflow_runs_not_a_list(github_service):
    """
    Edge Case: `workflow_runs` field exists but is not a list.
    """
    with patch("subprocess.run") as mock_run:
        # workflow_runs is a string, not a list
        mock_run.return_value = MagicMock(stdout='{"workflow_runs": "invalid_type"}', returncode=0)

        # Should return None because it's not a list
        status = github_service.get_latest_run_status("branch")
        assert status is None


def test_jobs_not_a_list(github_service):
    """
    Edge Case: `jobs` field exists but is not a list.
    """
    with patch("subprocess.run") as mock_run:
        # jobs is a string, not a list
        mock_run.return_value = MagicMock(stdout='{"jobs": "invalid_type"}', returncode=0)

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Invalid jobs structure: expected list"):
            github_service.get_run_logs("123")


def test_jobs_mixed_types(github_service):
    """
    Edge Case: `jobs` list contains mixed types (dicts and strings/None).
    """
    mixed_jobs = {
        "jobs": [
            "invalid_string_entry",
            None,
            {"id": 123, "conclusion": "failure"}
        ]
    }

    with patch("subprocess.run") as mock_run:
        def side_effect(args, **kwargs):
            # Mock jobs call
            if "jobs" in args[2] and "logs" not in args[2]:
                return MagicMock(stdout=json.dumps(mixed_jobs), returncode=0)
            # Mock logs call
            if "logs" in args[2]:
                return MagicMock(stdout="Log content", returncode=0)
            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect

        logs = github_service.get_run_logs("run_id")
        assert logs == "Log content"

        # Verify it filtered and found the valid dict job
        # (Implicitly verified by success, but we can check calls if needed)


def test_gh_api_returns_list_at_root(github_service):
    """
    Edge Case: `gh api` returns a list at the root instead of a dict.
    `get_latest_run_status` expects a dict with `workflow_runs`.
    If a list is returned, it should handle it gracefully (likely returning None).
    """
    with patch("subprocess.run") as mock_run:
        # API returns a list (e.g. `[]`)
        mock_run.return_value = MagicMock(stdout='[]', returncode=0)

        status = github_service.get_latest_run_status("branch")
        assert status is None
