import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from tenacity import RetryError

from coreason_git_automator.services.github import GitHubService


@pytest.fixture
def mock_shutil_which():
    with patch("shutil.which", return_value="/usr/bin/gh") as mock:
        yield mock


@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock:
        mock.return_value.returncode = 0
        mock.return_value.stdout = ""
        yield mock


@pytest.fixture
def github(mock_shutil_which):
    return GitHubService()


def test_init_raises_if_not_found():
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError):
            GitHubService()


def test_run_gh_command_success(github, mock_subprocess_run):
    """Test successful JSON command execution."""
    mock_subprocess_run.return_value.stdout = '{"key": "value"}'

    # We access the private method to test it directly or use a public method that calls it.
    # But _run_gh_command is private. However, public methods call it.
    # Let's test via get_latest_run_status for integration or access directly.
    # Accessing directly for unit testing is fine in Python.

    result = github._run_gh_command(["some", "args"])
    assert result == {"key": "value"}

    args = mock_subprocess_run.call_args[0][0]
    assert args == ["/usr/bin/gh", "some", "args"]


def test_run_gh_command_prohibited(github):
    """Test that 'run view' is prohibited."""
    with pytest.raises(RetryError) as excinfo:
        github._run_gh_command(["run", "view", "123"])

    assert isinstance(excinfo.value.last_attempt.exception(), RuntimeError)
    assert "Prohibited command" in str(excinfo.value.last_attempt.exception())


def test_run_gh_command_json_error(github, mock_subprocess_run):
    """Test handling of invalid JSON output."""
    mock_subprocess_run.return_value.stdout = "Not JSON"

    # _run_gh_command retries on RuntimeError?
    # No, it retries on exception.
    # json.JSONDecodeError raises RuntimeError inside the method.

    with pytest.raises(RetryError) as excinfo:
        github._run_gh_command(["api", "endpoint"])

    assert isinstance(excinfo.value.last_attempt.exception(), RuntimeError)
    assert "Failed to parse GitHub CLI output" in str(excinfo.value.last_attempt.exception())


def test_get_latest_run_status(github, mock_subprocess_run):
    """Test getting latest run status."""
    response = {"workflow_runs": [{"id": 123, "status": "queued", "conclusion": None}]}
    mock_subprocess_run.return_value.stdout = json.dumps(response)

    status = github.get_latest_run_status("main")

    assert status["id"] == 123
    assert status["databaseId"] == 123  # Should be polyfilled

    args = mock_subprocess_run.call_args[0][0]
    # Check that per_page=1 and branch=main are present
    assert any("branch=main" in arg for arg in args)


def test_get_latest_run_status_no_runs(github, mock_subprocess_run):
    """Test when no runs found."""
    mock_subprocess_run.return_value.stdout = '{"workflow_runs": []}'
    status = github.get_latest_run_status("main")
    assert status is None


def test_get_run_logs_success(github, mock_subprocess_run):
    """Test fetching logs for a failed job."""
    # First call: get jobs
    jobs_response = {
        "jobs": [
            {"id": 1, "conclusion": "success"},
            {"id": 2, "conclusion": "failure"},  # This is the target
            {"id": 3, "conclusion": "skipped"},
        ]
    }

    # Second call: get logs (text output)
    log_content = "Error: Something went wrong"

    # We need side_effect to return different values for sequential calls
    # Note: subprocess.run returns a CompletedProcess object

    proc_jobs = MagicMock()
    proc_jobs.returncode = 0
    proc_jobs.stdout = json.dumps(jobs_response)

    proc_logs = MagicMock()
    proc_logs.returncode = 0
    proc_logs.stdout = log_content

    mock_subprocess_run.side_effect = [proc_jobs, proc_logs]

    logs = github.get_run_logs("100")

    assert logs == log_content

    # Verify calls
    assert mock_subprocess_run.call_count == 2

    # First call checks
    args1 = mock_subprocess_run.call_args_list[0][0][0]
    assert "jobs" in args1[2]  # endpoint

    # Second call checks
    args2 = mock_subprocess_run.call_args_list[1][0][0]
    assert "jobs/2/logs" in args2[2]  # Correct job ID


def test_get_run_logs_no_failed_job(github, mock_subprocess_run):
    """Test fallback to last job if no failure found."""
    jobs_response = {"jobs": [{"id": 1, "conclusion": "success"}, {"id": 2, "conclusion": "success"}]}
    proc_jobs = MagicMock()
    proc_jobs.returncode = 0
    proc_jobs.stdout = json.dumps(jobs_response)

    proc_logs = MagicMock()
    proc_logs.returncode = 0
    proc_logs.stdout = "Logs"

    mock_subprocess_run.side_effect = [proc_jobs, proc_logs]

    github.get_run_logs("100")

    # Should fetch logs for job 2 (last one)
    args2 = mock_subprocess_run.call_args_list[1][0][0]
    assert "jobs/2/logs" in args2[2]


def test_create_pr_success(github, mock_subprocess_run):
    """Test PR creation."""
    response = {"html_url": "https://github.com/owner/repo/pull/1"}
    mock_subprocess_run.return_value.stdout = json.dumps(response)

    url = github.create_pr("Title", "Body", "head-branch")
    assert url == "https://github.com/owner/repo/pull/1"

    # Verify input JSON
    kwargs = mock_subprocess_run.call_args[1]
    input_json = json.loads(kwargs["input"])
    assert input_json["title"] == "Title"
    assert input_json["head"] == "head-branch"


def test_get_latest_run_status_invalid_structure(github, mock_subprocess_run):
    """Test when API returns invalid structure."""
    mock_subprocess_run.return_value.stdout = '{"workflow_runs": "not-a-list"}'
    status = github.get_latest_run_status("main")
    assert status is None


def test_get_run_logs_no_jobs(github, mock_subprocess_run):
    """Test when no jobs found."""
    mock_subprocess_run.return_value.stdout = '{"jobs": []}'
    with pytest.raises(RuntimeError, match="No jobs found"):
        github.get_run_logs("123")


def test_get_run_logs_invalid_jobs_structure(github, mock_subprocess_run):
    """Test when jobs is not a list."""
    mock_subprocess_run.return_value.stdout = '{"jobs": "not-list"}'
    with pytest.raises(RuntimeError, match="Invalid jobs structure"):
        github.get_run_logs("123")


def test_get_run_logs_missing_job_id(github, mock_subprocess_run):
    """Test when job has no ID."""
    jobs_response = {"jobs": [{"id": None, "conclusion": "failure"}]}
    mock_subprocess_run.return_value.stdout = json.dumps(jobs_response)
    with pytest.raises(RuntimeError, match="Job ID missing"):
        github.get_run_logs("123")


def test_create_pr_failure_no_url(github, mock_subprocess_run):
    """Test PR creation failure (no URL in response)."""
    mock_subprocess_run.return_value.stdout = "{}"
    with pytest.raises(RuntimeError, match="Failed to retrieve PR URL"):
        github.create_pr("t", "b", "h")


def test_create_pr_json_error(github, mock_subprocess_run):
    """Test PR creation JSON error."""
    mock_subprocess_run.return_value.stdout = "Not JSON"
    with pytest.raises(RuntimeError, match="Failed to parse GitHub CLI output"):
        github.create_pr("t", "b", "h")


def test_get_latest_run_status_missing_key(github, mock_subprocess_run):
    """Test when workflow_runs key is missing."""
    mock_subprocess_run.return_value.stdout = "{}"
    status = github.get_latest_run_status("main")
    assert status is None


def test_get_run_logs_no_valid_jobs(github, mock_subprocess_run):
    """Test when jobs list contains no valid dicts."""
    mock_subprocess_run.return_value.stdout = '{"jobs": ["string", 123]}'  # valid json list but invalid job objects
    with pytest.raises(RuntimeError, match="No valid job objects found"):
        github.get_run_logs("123")


def test_get_run_logs_missing_jobs_key(github, mock_subprocess_run):
    """Test when jobs key is missing."""
    mock_subprocess_run.return_value.stdout = "{}"
    with pytest.raises(RuntimeError, match="Could not retrieve jobs"):
        github.get_run_logs("123")


def test_run_gh_command_impl_failure(github, mock_subprocess_run):
    """Test that _run_gh_command_impl re-raises RuntimeError from run_command."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="error")
    # run_command raises RuntimeError when CalledProcessError occurs
    # _run_gh_command_impl catches it and re-raises

    with pytest.raises(RuntimeError, match="Command failed"):
        github._run_gh_command_impl(["some", "arg"])


def test_run_gh_command_impl_json_error(github, mock_subprocess_run):
    """Test that _run_gh_command_impl raises RuntimeError on JSON error."""
    mock_subprocess_run.return_value.stdout = "Not JSON"

    with pytest.raises(RuntimeError, match="Failed to parse GitHub CLI output"):
        github._run_gh_command_impl(["some", "arg"])


def test_run_gh_command_empty_output(github, mock_subprocess_run):
    """Test that empty output returns None."""
    mock_subprocess_run.return_value.stdout = "   "
    result = github._run_gh_command_impl(["some", "arg"])
    assert result is None
