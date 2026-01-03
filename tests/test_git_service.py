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
from git import GitCommandError

from coreason_git_automator.services.git import GitClient


@pytest.fixture
def mock_repo():
    with patch("coreason_git_automator.services.git.Repo") as mock:
        yield mock


@pytest.fixture
def git_client(mock_repo):
    return GitClient()


def test_init_success(mock_repo):
    GitClient()
    mock_repo.assert_called_with(".", search_parent_directories=True)


def test_init_failure(mock_repo):
    mock_repo.side_effect = Exception("Failed")
    with pytest.raises(RuntimeError, match="Failed to initialize"):
        GitClient()


def test_get_log_oneline(git_client):
    git_client.repo.git.log.return_value = "hash msg"
    assert git_client.get_log_oneline("main") == "hash msg"
    git_client.repo.git.log.assert_called_with("--oneline", "main")


def test_checkout(git_client):
    git_client.checkout("main")
    git_client.repo.git.checkout.assert_called_with("main")


def test_pull(git_client):
    git_client.pull()
    git_client.repo.git.pull.assert_called_once()


def test_create_branch(git_client):
    git_client.create_branch("feature")
    git_client.repo.git.checkout.assert_called_with("-b", "feature")


def test_merge_squash(git_client):
    git_client.merge_squash("feature")
    git_client.repo.git.merge.assert_called_with("--squash", "feature")


def test_commit(git_client):
    git_client.commit("Title", "Body")
    git_client.repo.git.commit.assert_called_with("-m", "Title\n\nBody")


def test_push(git_client):
    git_client.push("feature")
    git_client.repo.git.push.assert_called_with("-u", "origin", "feature")


def test_git_error_handling(git_client):
    git_client.repo.git.checkout.side_effect = GitCommandError("checkout", "error")
    with pytest.raises(RuntimeError, match="Failed to checkout"):
        git_client.checkout("invalid")


def test_get_log_oneline_error(git_client):
    git_client.repo.git.log.side_effect = GitCommandError("log", "error")
    with pytest.raises(RuntimeError, match="Failed to get git log"):
        git_client.get_log_oneline("main")


def test_pull_error(git_client):
    git_client.repo.git.pull.side_effect = GitCommandError("pull", "error")
    with pytest.raises(RuntimeError, match="Failed to pull"):
        git_client.pull()


def test_create_branch_error(git_client):
    git_client.repo.git.checkout.side_effect = GitCommandError("checkout -b", "error")
    with pytest.raises(RuntimeError, match="Failed to create branch"):
        git_client.create_branch("feature")


def test_merge_squash_error(git_client):
    git_client.repo.git.merge.side_effect = GitCommandError("merge --squash", "error")
    with pytest.raises(RuntimeError, match="Failed to merge squash"):
        git_client.merge_squash("feature")


def test_commit_error(git_client):
    git_client.repo.git.commit.side_effect = GitCommandError("commit", "error")
    with pytest.raises(RuntimeError, match="Failed to commit"):
        git_client.commit("Title", "Body")


def test_push_error(git_client):
    git_client.repo.git.push.side_effect = GitCommandError("push", "error")
    with pytest.raises(RuntimeError, match="Failed to push"):
        git_client.push("feature")
