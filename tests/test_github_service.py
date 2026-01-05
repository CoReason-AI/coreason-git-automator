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
from tenacity import RetryError

from coreason_git_automator.services.github import GitHubService


@pytest.fixture
def github_service():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        return GitHubService()


def test_verify_installed_success(github_service):
    with patch("shutil.which", return_value="/usr/bin/gh"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="gh version 2.40.0 (2023-10-24)\n", returncode=0)

            version = github_service.verify_installed()

            assert version == "gh version 2.40.0 (2023-10-24)"
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == ["/usr/bin/gh", "--version"]


def test_verify_installed_missing_executable(github_service):
    # Testing that verify_installed checks the executable via run_command
    # But since verify_installed calls run_command, and run_command executes the command,
    # if the executable is missing (and not caught by init), it fails.
    # However, ExternalTool catches missing executable in __init__.
    # So to test verify_installed failing, we must assume __init__ succeeded.
    pass  # Covered by test_verify_installed_command_error


def test_init_raises_if_missing():
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="Executable 'gh' not found in PATH"):
            GitHubService()


def test_verify_installed_command_error(github_service):
    with patch("shutil.which", return_value="/usr/bin/gh"):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["gh", "--version"], stderr="error")

            with pytest.raises(RuntimeError, match="Command failed"):
                github_service.verify_installed()


def test_get_latest_run_status_success(github_service):
    # Mocking `gh api ...` response structure
    mock_response = {"workflow_runs": [{"id": 123, "status": "completed", "conclusion": "success"}]}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=json.dumps(mock_response), returncode=0)

        status = github_service.get_latest_run_status("feature-branch")

        assert status == {"id": 123, "status": "completed", "conclusion": "success", "databaseId": 123}
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        # Should call `gh api ...`
        assert "gh" in args and "api" in args
        assert any("actions/runs" in arg for arg in args)


def test_get_latest_run_status_no_runs(github_service):
    mock_response = {"workflow_runs": []}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=json.dumps(mock_response), returncode=0)

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
    mock_response = {"html_url": "https://github.com/org/repo/pull/1"}
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=json.dumps(mock_response), returncode=0)

        url = github_service.create_pr("Title", "Body", "feature", "main")

        assert url == "https://github.com/org/repo/pull/1"
        mock_run.assert_called_once()
        # Ensure input was passed via stdin
        assert mock_run.call_args.kwargs["input"] is not None
        payload = json.loads(mock_run.call_args.kwargs["input"])
        assert payload["title"] == "Title"
        assert payload["body"] == "Body"


def test_command_failure_retry(github_service):
    # Test that it retries and eventually fails
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="Error message")

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                github_service.get_latest_run_status("branch")

        assert mock_run.call_count >= 3


def test_json_decode_error_retry(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Invalid JSON", returncode=0)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                github_service.get_latest_run_status("branch")

        assert mock_run.call_count >= 3


def test_create_pr_no_url(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

        with pytest.raises(RuntimeError, match="Failed to retrieve PR URL"):
            # create_pr calls subprocess directly now, so exception is raised directly
            github_service.create_pr("Title", "Body", "feature")


def test_get_run_logs_failure_no_retry(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="Log fetch failed")

        with pytest.raises(RuntimeError, match="Command failed"):
            github_service.get_run_logs("123")


def test_run_gh_command_empty_output(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="  \n ", returncode=0)

        result = github_service._run_gh_command(["some", "command"])
        assert result is None


def test_run_gh_command_primitive(github_service):
    # If API returns a primitive like true/false/null, current impl returns None for not-dict/not-list
    # Except list is returned.
    # json.loads("true") -> True (bool)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="true", returncode=0)

        result = github_service._run_gh_command(["some", "command"])
        assert result is None


def test_run_gh_command_empty_string(github_service):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=0)

        result = github_service._run_gh_command(["some", "command"])
        assert result is None


def test_run_gh_command_returns_list(github_service):
    """
    Cover line 60: return res (when list)
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="[1, 2]", returncode=0)
        result = github_service._run_gh_command(["some", "command"])
        assert result == [1, 2]


def test_create_pr_process_error(github_service):
    """
    Cover line 165-166: CalledProcessError in create_pr
    """
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="Failed")
        with pytest.raises(RuntimeError, match="Command failed"):
            github_service.create_pr("t", "b", "h")


def test_create_pr_json_error(github_service):
    """
    Cover line 168-169: JSONDecodeError in create_pr
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Invalid JSON", returncode=0)
        with pytest.raises(RuntimeError, match="Failed to parse GitHub CLI output"):
            github_service.create_pr("t", "b", "h")
