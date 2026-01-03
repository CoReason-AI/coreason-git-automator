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
from git import GitCommandError
from openai import APIError
from typer.testing import CliRunner

from coreason_git_automator.cli import app

runner = CliRunner()


@pytest.fixture
def mock_env(monkeypatch):
    """Sets required environment variables."""
    monkeypatch.setenv("JULES_API_KEY", "secret_jules")
    monkeypatch.setenv("GITHUB_TOKEN", "secret_gh")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret_ds")


@pytest.fixture
def mock_boundaries():
    """
    Mocks the external boundaries:
    - subprocess.run (for GitHub CLI, Jules CLI)
    - shutil.which (for Jules executable check)
    - GitPython (Repo)
    - OpenAI (Client)
    """
    with (
        patch("subprocess.run") as mock_sub,
        patch("shutil.which") as mock_which,
        patch("coreason_git_automator.services.git.Repo") as mock_repo,
        patch("coreason_git_automator.services.ai.OpenAI") as mock_openai,
    ):
        # Default behavior: Jules exists
        mock_which.return_value = "/usr/bin/jules"

        # Default subprocess behavior: success, empty stdout
        mock_sub.return_value = MagicMock(stdout="", returncode=0)

        # Default Git behavior
        mock_git = mock_repo.return_value.git
        mock_git.log.return_value = "hash1 feat: wip\nhash2 fix: bug"
        mock_git.checkout.return_value = ""
        mock_git.pull.return_value = ""
        mock_git.merge.return_value = ""
        mock_git.commit.return_value = ""
        mock_git.push.return_value = ""

        # Default OpenAI behavior
        mock_client = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "commit_title": "feat: new feature",
                            "commit_body": "- added feature",
                            "branch_name": "feat/new-feature",
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        yield mock_sub, mock_git, mock_client


def test_holistic_happy_path(mock_env, mock_boundaries):
    """
    Simulates a full successful run where CI passes immediately.
    """
    mock_sub, mock_git, mock_openai = mock_boundaries

    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args

        # 1. Jules Version
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        # 2. GitHub Run Status
        if "gh" in cmd_list and "run" in cmd_list and "list" in cmd_list:
            return MagicMock(
                stdout=json.dumps([{"status": "completed", "conclusion": "success", "databaseId": 12345}]),
                returncode=0,
            )

        # 3. GitHub PR Create
        if "gh" in cmd_list and "pr" in cmd_list and "create" in cmd_list:
            return MagicMock(
                stdout=json.dumps({"url": "https://github.com/org/repo/pull/1"}),
                returncode=0,
            )

        # Default for others (jules remote new)
        return MagicMock(stdout="", returncode=0)

    mock_sub.side_effect = side_effect

    # Run the CLI
    result = runner.invoke(app, ["start", "Build a spaceship"])

    # Assertions
    assert result.exit_code == 0
    assert "Found Jules version: 1.0.0" in result.stdout
    assert "CI passed!" in result.stdout
    assert "PR Created: https://github.com/org/repo/pull/1" in result.stdout

    # Verify Jules session started
    assert any(
        "/usr/bin/jules" in str(call) and "remote" in str(call) and "new" in str(call)
        for call in mock_sub.call_args_list
    )

    # Verify DeepSeek called
    mock_openai.chat.completions.create.assert_called_once()

    # Verify Git Push
    mock_git.push.assert_called_with("-u", "origin", "feat/new-feature")


def test_holistic_self_healing(mock_env, mock_boundaries):
    """
    Simulates a run where CI fails first, triggers feedback, and then passes.
    """
    mock_sub, mock_git, mock_openai = mock_boundaries

    class State:
        checked_once = False

    state = State()

    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args

        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        if "gh" in cmd_list and "run" in cmd_list and "list" in cmd_list:
            if not state.checked_once:
                state.checked_once = True
                return MagicMock(
                    stdout=json.dumps([{"status": "completed", "conclusion": "failure", "databaseId": 111}]),
                    returncode=0,
                )
            else:
                return MagicMock(
                    stdout=json.dumps([{"status": "completed", "conclusion": "success", "databaseId": 222}]),
                    returncode=0,
                )

        if "gh" in cmd_list and "run" in cmd_list and "view" in cmd_list:
            return MagicMock(stdout="Error: SyntaxError on line 10\n" * 10, returncode=0)

        if "/usr/bin/jules" in cmd_list and "remote" in cmd_list and "chat" in cmd_list:
            return MagicMock(stdout="", returncode=0)

        if "gh" in cmd_list and "pr" in cmd_list and "create" in cmd_list:
            return MagicMock(
                stdout=json.dumps({"url": "https://github.com/org/repo/pull/2"}),
                returncode=0,
            )

        return MagicMock(stdout="", returncode=0)

    mock_sub.side_effect = side_effect

    with patch("coreason_git_automator.cli.time.sleep"):
        result = runner.invoke(app, ["start", "Fix the bug"])

    assert result.exit_code == 0
    assert "CI failed (Run 111)" in result.stdout
    assert "Sending feedback to Jules..." in result.stdout
    assert "CI passed!" in result.stdout


def test_holistic_merge_conflict(mock_env, mock_boundaries):
    """
    Verifies that a git merge conflict is handled gracefully.
    """
    mock_sub, mock_git, mock_openai = mock_boundaries

    # Setup git merge to fail
    mock_git.merge.side_effect = GitCommandError("merge", "conflict")

    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)
        if "gh" in cmd_list and "run" in cmd_list and "list" in cmd_list:
            return MagicMock(
                stdout=json.dumps([{"status": "completed", "conclusion": "success", "databaseId": 1}]), returncode=0
            )
        return MagicMock(stdout="", returncode=0)

    mock_sub.side_effect = side_effect

    result = runner.invoke(app, ["start", "Task"])

    assert result.exit_code == 1
    assert "Git operation failed (Merge Conflict)" in result.stdout


def test_holistic_deepseek_api_failure(mock_env, mock_boundaries):
    """
    Verifies that persistent API failures from DeepSeek cause the CLI to exit with error.
    """
    mock_sub, mock_git, mock_openai = mock_boundaries

    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)
        if "gh" in cmd_list and "run" in cmd_list and "list" in cmd_list:
            return MagicMock(
                stdout=json.dumps([{"status": "completed", "conclusion": "success", "databaseId": 1}]), returncode=0
            )
        return MagicMock(stdout="", returncode=0)

    mock_sub.side_effect = side_effect

    # Make OpenAI fail
    mock_openai.chat.completions.create.side_effect = APIError("500 Server Error", request=MagicMock(), body={})

    with (
        patch("coreason_git_automator.cli.time.sleep"),
        patch("coreason_git_automator.services.ai.wait_exponential", return_value=0),
    ):
        result = runner.invoke(app, ["start", "Task"], catch_exceptions=True)

    assert result.exit_code == 1
    # Tenacity wraps the exception, so we check for the general error indicator
    assert "Error:" in result.stdout or "RetryError" in str(result.exception)
