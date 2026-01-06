# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from unittest.mock import patch

import pytest
from tenacity import RetryError

from coreason_git_automator.services.github import GitHubService


@pytest.fixture
def github_service():
    # We must ensure shutil.which returns a path so __init__ doesn't fail
    with patch("shutil.which", return_value="/usr/bin/gh"):
        yield GitHubService()


def test_verify_installed_success(github_service):
    # Verify it works
    with patch("coreason_git_automator.services.base.run_command", return_value="gh version 2.40.0"):
        # ExternalTool.verify_installed returns the output of `--version`
        assert github_service.verify_installed() == "gh version 2.40.0"


def test_verify_installed_missing_executable(github_service):
    # So to test verify_installed failing, we must assume __init__ succeeded.
    pass  # Covered by test_verify_installed_command_error


def test_init_raises_if_missing():
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="Executable 'gh' not found in PATH"):
            GitHubService()


def test_verify_installed_command_error(github_service):
    with patch("coreason_git_automator.services.base.run_command", side_effect=RuntimeError("Command failed")):
        # verify_installed calls self.executable --version.
        # It should propagate the RuntimeError if run_command fails.
        with pytest.raises(RuntimeError, match="Command failed"):
            github_service.verify_installed()


def test_get_latest_run_status_success(github_service):
    mock_response = {"workflow_runs": [{"id": 12345, "status": "completed", "conclusion": "success"}]}

    with patch.object(github_service, "_run_gh_command", return_value=mock_response) as mock_run:
        status = github_service.get_latest_run_status("feature-branch")
        assert status is not None
        assert status["databaseId"] == 12345
        assert status["conclusion"] == "success"
        mock_run.assert_called_with(["api", "repos/:owner/:repo/actions/runs?branch=feature-branch&per_page=1"])


def test_get_latest_run_status_no_runs(github_service):
    mock_response = {"workflow_runs": []}
    with patch.object(github_service, "_run_gh_command", return_value=mock_response):
        status = github_service.get_latest_run_status("new-branch")
        assert status is None


def test_get_run_logs_success(github_service):
    """
    Test get_run_logs fetches jobs, finds failed job, and fetches logs using API.
    """
    run_id = "123"
    job_id = 999

    # Mock jobs response with a failed job
    mock_jobs_response = {"jobs": [{"id": 101, "conclusion": "success"}, {"id": job_id, "conclusion": "failure"}]}

    with patch.object(github_service, "_run_gh_command", return_value=mock_jobs_response) as mock_get_jobs:
        with patch("coreason_git_automator.services.github.run_command") as mock_run_cmd:
            mock_run_cmd.return_value = "Log content from API"

            logs = github_service.get_run_logs(run_id)

            assert logs == "Log content from API"

            # Verify jobs call
            mock_get_jobs.assert_called_with(["api", f"repos/:owner/:repo/actions/runs/{run_id}/jobs"])

            # Verify logs call - strictly API-first
            mock_run_cmd.assert_called_with(["gh", "api", f"repos/:owner/:repo/actions/jobs/{job_id}/logs"])


def test_get_run_logs_fallback_last_job(github_service):
    """
    Test fallback to last job if no failed job found.
    """
    run_id = "123"
    job_id = 102

    # Mock jobs response with no explicitly failed job (e.g. cancelled)
    mock_jobs_response = {"jobs": [{"id": 101, "conclusion": "success"}, {"id": job_id, "conclusion": "cancelled"}]}

    with patch.object(github_service, "_run_gh_command", return_value=mock_jobs_response):
        with patch("coreason_git_automator.services.github.run_command") as mock_run_cmd:
            mock_run_cmd.return_value = "Log content"

            github_service.get_run_logs(run_id)

            # Should fetch logs for the last job (102)
            mock_run_cmd.assert_called_with(["gh", "api", f"repos/:owner/:repo/actions/jobs/{job_id}/logs"])


def test_get_run_logs_no_jobs(github_service):
    run_id = "123"
    mock_jobs_response = {"jobs": []}

    with patch.object(github_service, "_run_gh_command", return_value=mock_jobs_response):
        with pytest.raises(RuntimeError, match=f"No jobs found for run {run_id}"):
            github_service.get_run_logs(run_id)


def test_get_run_logs_jobs_failure(github_service):
    """Test when fetching jobs fails (returns None or missing key)."""
    run_id = "123"
    with patch.object(github_service, "_run_gh_command", return_value=None):
        with pytest.raises(RuntimeError, match=f"Could not retrieve jobs for run {run_id}"):
            github_service.get_run_logs(run_id)


def test_get_run_logs_missing_job_id(github_service):
    """Test case where the target job has no ID."""
    run_id = "123"
    # Job has no 'id' field
    mock_jobs_response = {"jobs": [{"conclusion": "failure"}]}

    with patch.object(github_service, "_run_gh_command", return_value=mock_jobs_response):
        with pytest.raises(RuntimeError, match="Job ID missing from API response"):
            github_service.get_run_logs(run_id)


def test_create_pr_success(github_service):
    mock_response = '{"html_url": "https://github.com/owner/repo/pull/1"}'
    with patch("coreason_git_automator.services.github.run_command", return_value=mock_response) as mock_run:
        url = github_service.create_pr("Title", "Body", "head-branch")
        assert url == "https://github.com/owner/repo/pull/1"
        # Verify args
        # Note: We can't easily inspect input_text passed to run_command with simple assert_called_with
        # But we can check the command args
        mock_run.assert_called()
        args, kwargs = mock_run.call_args
        assert args[0] == ["gh", "api", "repos/:owner/:repo/pulls", "--method", "POST", "--input", "-"]


def test_command_failure_retry(github_service):
    with patch("coreason_git_automator.services.github.run_command", side_effect=RuntimeError("Fail")):
        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                github_service.get_latest_run_status("branch")


def test_json_decode_error_retry(github_service):
    with patch("coreason_git_automator.services.github.run_command", return_value="Invalid JSON"):
        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                github_service.get_latest_run_status("branch")


def test_create_pr_no_url(github_service):
    with patch("coreason_git_automator.services.github.run_command", return_value="{}"):
        with pytest.raises(RuntimeError, match="Failed to retrieve PR URL"):
            github_service.create_pr("t", "b", "h")


def test_get_run_logs_fetch_failure(github_service):
    """Test failure when fetching the actual log content."""
    mock_jobs_response = {"jobs": [{"id": 1, "conclusion": "failure"}]}

    with patch.object(github_service, "_run_gh_command", return_value=mock_jobs_response):
        with patch("coreason_git_automator.services.github.run_command", side_effect=RuntimeError("Log fetch failed")):
            with pytest.raises(RuntimeError, match="Log fetch failed"):
                github_service.get_run_logs("123")


def test_run_gh_command_empty_output(github_service):
    with patch("coreason_git_automator.services.github.run_command", return_value="   "):
        assert github_service._run_gh_command(["test"]) is None


def test_run_gh_command_primitive(github_service):
    # gh api usually returns objects or arrays. If it returned a primitive,
    # _run_gh_command returns None (as per `if isinstance(res, dict)` check, and `list` check added implicitly?)
    # Wait, the code says:
    # if isinstance(res, dict): return res
    # if isinstance(res, list): return res
    # return None
    with patch("coreason_git_automator.services.github.run_command", return_value="123"):
        assert github_service._run_gh_command(["test"]) is None


def test_run_gh_command_empty_string(github_service):
    # Verify behavior when run_command returns empty string
    with patch("coreason_git_automator.services.github.run_command", return_value=""):
        assert github_service._run_gh_command(["test"]) is None


def test_run_gh_command_returns_list(github_service):
    with patch("coreason_git_automator.services.github.run_command", return_value="[]"):
        assert github_service._run_gh_command(["test"]) == []


def test_create_pr_process_error(github_service):
    with patch("coreason_git_automator.services.github.run_command", side_effect=RuntimeError("Command failed")):
        with pytest.raises(RuntimeError, match="Command failed"):
            github_service.create_pr("t", "b", "h")


def test_create_pr_json_error(github_service):
    with patch("coreason_git_automator.services.github.run_command", return_value="Invalid"):
        with pytest.raises(RuntimeError, match="Failed to parse GitHub CLI output"):
            github_service.create_pr("t", "b", "h")
