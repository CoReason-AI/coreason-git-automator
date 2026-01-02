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
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from coreason_git_automator.services.github import GitHubService


@pytest.fixture
def github_service():
    return GitHubService()


def test_get_latest_run_status_success(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps([{"status": "completed", "conclusion": "success", "databaseId": 123}]), returncode=0
        )

        status = github_service.get_latest_run_status("feature-branch")

        assert status == {"status": "completed", "conclusion": "success", "databaseId": 123}
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "gh" in args and "run" in args and "list" in args


def test_get_latest_run_status_no_runs(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="[]", returncode=0)

        status = github_service.get_latest_run_status("new-branch")

        assert status is None


def test_get_run_logs_success(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Log content...", returncode=0)

        logs = github_service.get_run_logs("123")

        assert logs == "Log content..."
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "gh" in args and "run" in args and "view" in args and "--log" in args


def test_create_pr_success(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"url": "https://github.com/org/repo/pull/1"}), returncode=0
        )

        url = github_service.create_pr("Title", "Body", "feature", "main")

        assert url == "https://github.com/org/repo/pull/1"


def test_command_failure(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="Error message")

        with pytest.raises(RuntimeError, match="GitHub CLI command failed"):
            github_service.get_latest_run_status("branch")


def test_json_decode_error(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Invalid JSON", returncode=0)

        with pytest.raises(RuntimeError, match="Failed to parse GitHub CLI output"):
            github_service.get_latest_run_status("branch")


def test_create_pr_no_url(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

        with pytest.raises(RuntimeError, match="Failed to retrieve PR URL"):
            github_service.create_pr("Title", "Body", "feature")


def test_get_run_logs_failure(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="Log fetch failed")

        with pytest.raises(RuntimeError, match="Failed to fetch logs"):
            github_service.get_run_logs("123")


def test_run_gh_command_empty_output(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="  \n ", returncode=0)

        result = github_service._run_gh_command(["some", "command"])
        assert result is None
