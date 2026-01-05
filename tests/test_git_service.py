# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from coreason_git_automator.services.git import GitClient


@pytest.fixture
def git_client():
    return GitClient()


def test_run_success(git_client):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="output", returncode=0)

        result = git_client.run(["status"])

        assert result == "output"
        mock_run.assert_called_once()


def test_run_failure(git_client):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"], stderr="Error")

        with pytest.raises(RuntimeError, match="Command failed"):
            git_client.run(["status"])


def test_checkout(git_client):
    with patch.object(git_client, "run") as mock_run:
        git_client.checkout("main")
        mock_run.assert_called_with(["checkout", "main"])


def test_pull(git_client):
    with patch.object(git_client, "run") as mock_run:
        git_client.pull()
        mock_run.assert_called_with(["pull"])


def test_create_branch(git_client):
    with patch.object(git_client, "run") as mock_run:
        git_client.create_branch("feature")
        mock_run.assert_called_with(["checkout", "-b", "feature"])


def test_ensure_branch_existing(git_client):
    """Test ensure_branch when branch already exists."""
    with patch.object(git_client, "run") as mock_run:
        git_client.ensure_branch("feature")
        # Should just checkout
        mock_run.assert_called_once_with(["checkout", "feature"])


def test_ensure_branch_missing(git_client):
    """Test ensure_branch when branch does not exist."""
    with patch.object(git_client, "run") as mock_run:
        # First call fails (checkout), second call succeeds (create)
        # We need to simulate RuntimeError on first call
        mock_run.side_effect = [RuntimeError("Failed"), None]

        git_client.ensure_branch("feature")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(["checkout", "feature"])
        mock_run.assert_any_call(["checkout", "-b", "feature"])


def test_merge_squash(git_client):
    with patch.object(git_client, "run") as mock_run:
        git_client.merge_squash("feature")
        mock_run.assert_called_with(["merge", "--squash", "feature"])


def test_commit(git_client):
    with patch.object(git_client, "run") as mock_run:
        git_client.commit("Title", "Body")
        mock_run.assert_called_with(["commit", "-m", "Title\n\nBody"])


def test_push(git_client):
    with patch.object(git_client, "run") as mock_run:
        git_client.push("feature")
        mock_run.assert_called_with(["push", "-u", "origin", "feature"])


def test_get_log_oneline(git_client):
    with patch.object(git_client, "run") as mock_run:
        mock_run.return_value = "log"
        assert git_client.get_log_oneline("branch") == "log"
        mock_run.assert_called_with(["log", "--oneline", "branch"])
