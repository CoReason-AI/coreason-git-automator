import subprocess
from unittest.mock import patch

import pytest
from tenacity import RetryError

from coreason_git_automator.services.git import GitClient
from coreason_git_automator.services.github import GitHubService
from coreason_git_automator.services.jules import JulesWrapper


@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock:
        mock.return_value.stdout = ""
        mock.return_value.returncode = 0
        yield mock


@pytest.fixture
def jules():
    with patch("shutil.which", return_value="/usr/bin/jules"):
        yield JulesWrapper()


@pytest.fixture
def git():
    return GitClient()


@pytest.fixture
def github():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        yield GitHubService()


def test_jules_broken_symlink_context(jules, mock_subprocess_run, tmp_path):
    """
    Edge Case: Context file is a broken symlink.
    Should be skipped gracefully (warning logged), not crash.
    """
    broken_link = tmp_path / "broken_link.py"
    try:
        broken_link.symlink_to("non_existent_target")
    except OSError:
        pytest.skip("Symlinks not supported on this platform")

    jules.run_session("prompt", context_files=[broken_link])

    # Verify call made, prompt contains [INSTRUCTION] but NOT [CONTEXT: broken_link]
    # (Because reading failed)
    args = mock_subprocess_run.call_args[0][0]
    prompt = args[3]
    assert "[INSTRUCTION]" in prompt
    assert f"[CONTEXT: {broken_link}]" not in prompt


def test_git_client_run_command_encoding_robustness(git):
    """
    Edge Case: Verify that run_command uses robust encoding handling.
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "ok"
        mock_run.return_value.returncode = 0

        git.get_log_oneline("main")

        # Verify call args contain errors="replace"
        kwargs = mock_run.call_args[1]
        assert kwargs.get("errors") == "replace"
        assert kwargs.get("encoding") == "utf-8"


def test_github_404_retry_failure(github, mock_subprocess_run):
    """
    Edge Case: GitHub API returns 404 (Repo not found).
    Should retry (in case of flake) then fail with RetryError wrapping RuntimeError.
    """
    # 404 typically causes gh cli to exit with non-zero
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="HTTP 404: Not Found"
    )

    with patch("tenacity.nap.time.sleep"):  # Skip sleep
        with pytest.raises(RetryError) as excinfo:
            github.get_latest_run_status("main")

    assert isinstance(excinfo.value.last_attempt.exception(), RuntimeError)
    assert "Command failed" in str(excinfo.value.last_attempt.exception())
    assert "HTTP 404" in str(excinfo.value.last_attempt.exception())


def test_github_rate_limit_retry(github, mock_subprocess_run):
    """
    Edge Case: GitHub API returns 429 or secondary rate limit.
    """
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["gh"], stderr="HTTP 429: Rate limit exceeded"
    )

    with patch("tenacity.nap.time.sleep"):
        with pytest.raises(RetryError):
            github.get_latest_run_status("main")
