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
    - subprocess.run (for Git, GitHub CLI, Jules CLI)
    - httpx.Client (for DeepSeek API)
    - shutil.which (for Jules executable check)
    """
    with (
        patch("subprocess.run") as mock_sub,
        patch("httpx.Client") as mock_http,
        patch("shutil.which") as mock_which,
    ):
        # Default behavior: Jules exists
        mock_which.return_value = "/usr/bin/jules"

        # Default subprocess behavior: success, empty stdout
        mock_sub.return_value = MagicMock(stdout="", returncode=0)

        # Default HTTP behavior (DeepSeek)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "commit_title": "feat: new feature",
                            "commit_body": "- added feature",
                            "branch_name": "feat/new-feature",
                        })
                    }
                }
            ]
        }
        mock_response.status_code = 200
        mock_http_instance = mock_http.return_value
        mock_http_instance.__enter__.return_value.post.return_value = mock_response

        yield mock_sub, mock_http_instance


def test_holistic_happy_path(mock_env, mock_boundaries):
    """
    Simulates a full successful run where CI passes immediately.
    """
    mock_run, mock_http = mock_boundaries

    def side_effect(args, **kwargs):
        # args is typically a list of strings
        cmd_list = args if isinstance(args, list) else args
        cmd_str = " ".join(str(x) for x in cmd_list)

        # 1. Jules Version
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        # 2. GitHub Run Status
        if "gh" in cmd_list and "run" in cmd_list and "list" in cmd_list:
            # Simulate Success immediately
            return MagicMock(
                stdout=json.dumps(
                    [{"status": "completed", "conclusion": "success", "databaseId": 12345}]
                ),
                returncode=0,
            )

        # 3. Git Log
        if "git" in cmd_list and "log" in cmd_list:
            return MagicMock(stdout="hash1 feat: wip\nhash2 fix: bug", returncode=0)

        # 4. GitHub PR Create
        if "gh" in cmd_list and "pr" in cmd_list and "create" in cmd_list:
            return MagicMock(
                stdout=json.dumps({"url": "https://github.com/org/repo/pull/1"}),
                returncode=0,
            )

        # Default for others (git checkout, merge, push, jules remote new)
        return MagicMock(stdout="", returncode=0)

    mock_run.side_effect = side_effect

    # Run the CLI
    result = runner.invoke(app, ["start", "Build a spaceship"])

    # Assertions
    assert result.exit_code == 0
    assert "Found Jules version: 1.0.0" in result.stdout
    assert "CI passed!" in result.stdout
    assert "PR Created: https://github.com/org/repo/pull/1" in result.stdout

    # Verify Jules session started (subprocess call)
    assert any(
        "/usr/bin/jules" in str(call) and "remote" in str(call) and "new" in str(call)
        for call in mock_run.call_args_list
    )

    # Verify DeepSeek called (httpx call)
    mock_http.__enter__.return_value.post.assert_called_once()

    # Verify Git Push (subprocess call)
    assert any(
        "git" in str(call) and "push" in str(call) for call in mock_run.call_args_list
    )


def test_holistic_self_healing(mock_env, mock_boundaries):
    """
    Simulates a run where CI fails first, triggers feedback, and then passes.
    """
    mock_run, mock_http = mock_boundaries

    # State to toggle CI result
    class State:
        checked_once = False

    state = State()

    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args
        cmd_str = " ".join(str(x) for x in cmd_list)

        # 1. Jules Version
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        # 2. GitHub Run Status
        if "gh" in cmd_list and "run" in cmd_list and "list" in cmd_list:
            if not state.checked_once:
                state.checked_once = True
                # Fail first time
                return MagicMock(
                    stdout=json.dumps(
                        [{"status": "completed", "conclusion": "failure", "databaseId": 111}]
                    ),
                    returncode=0,
                )
            else:
                # Success second time
                return MagicMock(
                    stdout=json.dumps(
                        [{"status": "completed", "conclusion": "success", "databaseId": 222}]
                    ),
                    returncode=0,
                )

        # 3. GitHub Run Logs
        if "gh" in cmd_list and "run" in cmd_list and "view" in cmd_list:
            return MagicMock(
                stdout="Error: SyntaxError on line 10\n" * 10, returncode=0
            )

        # 4. Jules Chat (Feedback)
        if "/usr/bin/jules" in cmd_list and "remote" in cmd_list and "chat" in cmd_list:
            return MagicMock(stdout="", returncode=0)

        # 5. Git Log
        if "git" in cmd_list and "log" in cmd_list:
            return MagicMock(stdout="hash1 fix: syntax", returncode=0)

        # 6. GitHub PR Create
        if "gh" in cmd_list and "pr" in cmd_list and "create" in cmd_list:
            return MagicMock(
                stdout=json.dumps({"url": "https://github.com/org/repo/pull/2"}),
                returncode=0,
            )

        return MagicMock(stdout="", returncode=0)

    mock_run.side_effect = side_effect

    # Patch time.sleep to speed up test execution
    with patch("coreason_git_automator.cli.time.sleep"):
        result = runner.invoke(app, ["start", "Fix the bug"])

    # Assertions
    assert result.exit_code == 0
    assert "CI failed (Run 111)" in result.stdout
    assert "Sending feedback to Jules..." in result.stdout
    assert "CI passed!" in result.stdout

    # Verify feedback sent
    feedback_calls = [
        c for c in mock_run.call_args_list if "/usr/bin/jules" in str(c) and "chat" in str(c)
    ]
    assert len(feedback_calls) == 1
    # Check that logs were passed (we mocked logs with "SyntaxError")
    assert "SyntaxError" in str(feedback_calls[0])
