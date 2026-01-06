from unittest.mock import patch

import pytest

from coreason_git_automator.services.git import GitClient


@pytest.fixture
def mock_run_command():
    with patch("coreason_git_automator.services.git.run_command") as mock:
        yield mock


@pytest.fixture
def git(mock_run_command):
    return GitClient()


def test_run(git, mock_run_command):
    git.run(["status"])
    mock_run_command.assert_called_with(["git", "status"])


def test_get_log_oneline(git, mock_run_command):
    mock_run_command.return_value = "hash commit message"
    log = git.get_log_oneline("branch")
    assert log == "hash commit message"
    mock_run_command.assert_called_with(["git", "log", "--oneline", "branch"])


def test_checkout(git, mock_run_command):
    git.checkout("branch")
    mock_run_command.assert_called_with(["git", "checkout", "branch"])


def test_pull(git, mock_run_command):
    git.pull()
    mock_run_command.assert_called_with(["git", "pull"])


def test_create_branch(git, mock_run_command):
    git.create_branch("new-branch")
    mock_run_command.assert_called_with(["git", "checkout", "-b", "new-branch"])


def test_ensure_branch_exists(git, mock_run_command):
    """Test ensuring branch when it already exists."""
    git.ensure_branch("existing")
    mock_run_command.assert_called_with(["git", "checkout", "existing"])


def test_ensure_branch_not_exists(git, mock_run_command):
    """Test ensuring branch when it needs creation."""
    # First call fails (checkout), second succeeds (create)
    mock_run_command.side_effect = [RuntimeError("Not found"), None]

    git.ensure_branch("new-branch")

    assert mock_run_command.call_count == 2
    assert mock_run_command.call_args_list[0][0][0] == ["git", "checkout", "new-branch"]
    assert mock_run_command.call_args_list[1][0][0] == ["git", "checkout", "-b", "new-branch"]


def test_merge_squash(git, mock_run_command):
    git.merge_squash("feature")
    mock_run_command.assert_called_with(["git", "merge", "--squash", "feature"])


def test_commit(git, mock_run_command):
    git.commit("title", "body")
    mock_run_command.assert_called_with(["git", "commit", "-m", "title\n\nbody"])


def test_push(git, mock_run_command):
    git.push("branch")
    mock_run_command.assert_called_with(["git", "push", "-u", "origin", "branch"])
