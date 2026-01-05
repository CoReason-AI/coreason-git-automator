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
        patch("tenacity.nap.time.sleep"),  # Skip tenacity sleeps
        patch("coreason_git_automator.services.workflow.time.sleep"),  # Skip workflow sleeps
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
                        "content": json.dumps(
                            {
                                "commit_title": "feat: new feature",
                                "commit_body": "- added feature",
                                "branch_name": "feat/new-feature",
                            }
                        )
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

        # 1. Jules Version
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        # 2. GitHub Run Status (Updated to gh api)
        if "gh" in cmd_list and "api" in cmd_list and any("actions/runs" in a for a in cmd_list):
            # Simulate Success immediately
            # The code expects {"workflow_runs": [{"id": ..., "status": ..., "conclusion": ...}]}
            return MagicMock(
                stdout=json.dumps({"workflow_runs": [{"status": "completed", "conclusion": "success", "id": 12345}]}),
                returncode=0,
            )

        # 3. Git Log
        if "git" in cmd_list and "log" in cmd_list:
            return MagicMock(stdout="hash1 feat: wip\nhash2 fix: bug", returncode=0)

        # 4. GitHub PR Create (Updated to gh api)
        if "gh" in cmd_list and "api" in cmd_list and any("pulls" in a for a in cmd_list) and "--method" in cmd_list:
            # The code passes input via stdin, and expects response with html_url
            return MagicMock(
                stdout=json.dumps({"html_url": "https://github.com/org/repo/pull/1"}),
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
    assert any("git" in str(call) and "push" in str(call) for call in mock_run.call_args_list)


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

        # 1. Jules Version
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        # 2. GitHub Run Status (API)
        if "gh" in cmd_list and "api" in cmd_list and any("actions/runs" in a for a in cmd_list):
            if not state.checked_once:
                state.checked_once = True
                # Fail first time
                return MagicMock(
                    stdout=json.dumps({"workflow_runs": [{"status": "completed", "conclusion": "failure", "id": 111}]}),
                    returncode=0,
                )
            else:
                # Success second time
                return MagicMock(
                    stdout=json.dumps({"workflow_runs": [{"status": "completed", "conclusion": "success", "id": 222}]}),
                    returncode=0,
                )

        # 3. GitHub Run Logs (gh run view is still used)
        if "gh" in cmd_list and "run" in cmd_list and "view" in cmd_list:
            return MagicMock(stdout="Error: SyntaxError on line 10\n" * 10, returncode=0)

        # 4. Jules Chat (Feedback)
        if "/usr/bin/jules" in cmd_list and "remote" in cmd_list and "chat" in cmd_list:
            return MagicMock(stdout="", returncode=0)

        # 5. Git Log
        if "git" in cmd_list and "log" in cmd_list:
            return MagicMock(stdout="hash1 fix: syntax", returncode=0)

        # 6. GitHub PR Create (API)
        if "gh" in cmd_list and "api" in cmd_list and any("pulls" in a for a in cmd_list):
            return MagicMock(
                stdout=json.dumps({"html_url": "https://github.com/org/repo/pull/2"}),
                returncode=0,
            )

        return MagicMock(stdout="", returncode=0)

    mock_run.side_effect = side_effect

    # Patch time.sleep to speed up test execution
    with patch("coreason_git_automator.services.workflow.time.sleep"):
        result = runner.invoke(app, ["start", "Fix the bug"])

    # Assertions
    assert result.exit_code == 0
    assert "CI failed (Run 111)" in result.stdout
    assert "Sending feedback to Jules..." in result.stdout
    assert "CI passed!" in result.stdout

    # Verify feedback sent
    feedback_calls = [c for c in mock_run.call_args_list if "/usr/bin/jules" in str(c) and "chat" in str(c)]
    assert len(feedback_calls) == 1
    # Check that logs were passed (we mocked logs with "SyntaxError")
    assert "SyntaxError" in str(feedback_calls[0])


def test_holistic_context_injection(mock_env, mock_boundaries, tmp_path):
    """
    Verifies that context files are read and injected into the Jules prompt.
    """
    mock_run, _ = mock_boundaries

    # Create a dummy file
    context_file = tmp_path / "extra.py"
    context_file.write_text("print('hello world')")

    def side_effect(args, **kwargs):
        return MagicMock(stdout="1.0.0", returncode=0)

    mock_run.side_effect = side_effect

    with patch("coreason_git_automator.services.workflow.time.sleep"):
        # We only care about the initial Jules call for this test.
        # But we must ensure it doesn't crash on subsequent calls if monitoring is on.
        # So we mock a quick success.
        def side_effect_complete(args, **kwargs):
            cmd_list = args if isinstance(args, list) else args
            # GH Status
            if "gh" in cmd_list and "api" in cmd_list and any("actions/runs" in a for a in cmd_list):
                return MagicMock(
                    stdout=json.dumps({"workflow_runs": [{"status": "completed", "conclusion": "success", "id": 999}]}),
                    returncode=0,
                )
            if "git" in cmd_list:  # allow git log/merge/push
                return MagicMock(stdout="log", returncode=0)
            # GH PR
            if "gh" in cmd_list and "api" in cmd_list and any("pulls" in a for a in cmd_list):
                return MagicMock(
                    stdout=json.dumps({"html_url": "http://pr"}),
                    returncode=0,
                )
            # Jules version
            if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
                return MagicMock(stdout="1.0.0", returncode=0)

            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect_complete

        runner.invoke(app, ["start", "Task", "--context", str(context_file)])

    # Verify the Jules call contains the file content
    jules_calls = [
        c for c in mock_run.call_args_list if "/usr/bin/jules" in str(c) and "remote" in str(c) and "new" in str(c)
    ]
    assert len(jules_calls) == 1

    # The last argument to `jules remote new` is the prompt
    # args[0] is the list of command arguments
    prompt_arg = jules_calls[0][0][0][-1]

    assert f"[CONTEXT: {context_file}]" in prompt_arg
    assert "print('hello world')" in prompt_arg
    assert "[INSTRUCTION]" in prompt_arg


def test_holistic_persistent_failure(mock_env, mock_boundaries):
    """
    Verifies the feedback loop handles multiple failures before success.
    """
    mock_run, _ = mock_boundaries

    class State:
        failures = 0

    state = State()

    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args

        # Jules Version
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        # GH Run Status
        if "gh" in cmd_list and "api" in cmd_list and any("actions/runs" in a for a in cmd_list):
            if state.failures < 2:
                state.failures += 1
                return MagicMock(
                    stdout=json.dumps(
                        {
                            "workflow_runs": [
                                {"status": "completed", "conclusion": "failure", "id": 100 + state.failures}
                            ]
                        }
                    ),
                    returncode=0,
                )
            return MagicMock(
                stdout=json.dumps({"workflow_runs": [{"status": "completed", "conclusion": "success", "id": 200}]}),
                returncode=0,
            )

        # GH Logs
        if "gh" in cmd_list and "run" in cmd_list and "view" in cmd_list:
            return MagicMock(stdout="Error log...", returncode=0)

        # Git/PR default
        if "git" in cmd_list:
            if "log" in cmd_list:
                return MagicMock(stdout="log", returncode=0)
            return MagicMock(stdout="", returncode=0)

        if "gh" in cmd_list and "api" in cmd_list and any("pulls" in a for a in cmd_list):
            return MagicMock(
                stdout=json.dumps({"html_url": "http://pr"}),
                returncode=0,
            )

        return MagicMock(stdout="", returncode=0)

    mock_run.side_effect = side_effect

    with patch("coreason_git_automator.services.workflow.time.sleep"):
        result = runner.invoke(app, ["start", "Task"])

    assert result.exit_code == 0
    # Should have failed twice
    assert "CI failed (Run 101)" in result.stdout
    assert "CI failed (Run 102)" in result.stdout
    assert "CI passed!" in result.stdout

    # Check feedback calls
    feedback_calls = [c for c in mock_run.call_args_list if "/usr/bin/jules" in str(c) and "chat" in str(c)]
    assert len(feedback_calls) == 2


def test_holistic_merge_conflict(mock_env, mock_boundaries):
    """
    Verifies that a git merge conflict is handled gracefully.
    """
    mock_run, _ = mock_boundaries

    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args

        # Jules Version
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)

        # GH Success
        if "gh" in cmd_list and "api" in cmd_list and any("actions/runs" in a for a in cmd_list):
            return MagicMock(
                stdout=json.dumps({"workflow_runs": [{"status": "completed", "conclusion": "success", "id": 1}]}),
                returncode=0,
            )

        # Git Merge -> Conflict
        if "git" in cmd_list and "merge" in cmd_list:
            raise subprocess.CalledProcessError(1, cmd_list, stderr="CONFLICT (content): Merge conflict")

        # Git Log (needed before merge)
        if "git" in cmd_list and "log" in cmd_list:
            return MagicMock(stdout="log", returncode=0)

        return MagicMock(stdout="", returncode=0)

    mock_run.side_effect = side_effect

    result = runner.invoke(app, ["start", "Task"])

    assert result.exit_code == 1
    assert "Git operation failed (Merge Conflict)" in result.stdout


def test_holistic_deepseek_api_failure(mock_env, mock_boundaries):
    """
    Verifies that persistent API failures from DeepSeek cause the CLI to exit with error.
    """
    mock_run, mock_http = mock_boundaries

    # Setup GH/Git success so we reach the DeepSeek step
    def side_effect(args, **kwargs):
        cmd_list = args if isinstance(args, list) else args
        if "/usr/bin/jules" in cmd_list and "--version" in cmd_list:
            return MagicMock(stdout="1.0.0", returncode=0)
        if "gh" in cmd_list and "api" in cmd_list and any("actions/runs" in a for a in cmd_list):
            return MagicMock(
                stdout=json.dumps({"workflow_runs": [{"status": "completed", "conclusion": "success", "id": 1}]}),
                returncode=0,
            )
        if "git" in cmd_list and "log" in cmd_list:
            return MagicMock(stdout="log", returncode=0)
        return MagicMock(stdout="", returncode=0)

    mock_run.side_effect = side_effect

    # Setup DeepSeek failure
    import httpx

    mock_post = mock_http.__enter__.return_value.post
    mock_post.side_effect = httpx.HTTPError("500 Server Error")

    with (
        patch("coreason_git_automator.services.workflow.time.sleep"),
        patch("coreason_git_automator.services.ai.wait_exponential", return_value=0),
    ):
        # Explicitly set catch_exceptions=True (even though it is default) to handle RetryError bubbling
        result = runner.invoke(app, ["start", "Task"], catch_exceptions=True)

    assert result.exit_code == 1
    # Check that the error was caught and logged
    # If exit_code is 1, it might be due to the exception not being caught (handled by click)
    # OR it might be our "raise typer.Exit(code=1)"
    # We check stdout for our custom error message
    assert (
        "DeepSeek API error" in result.stdout or "Error: Unexpected error" in result.stdout or "Error:" in result.stdout
    )
