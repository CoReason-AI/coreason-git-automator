# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from coreason_git_automator.cli import app
from coreason_git_automator.models import DeepSeekCommit

runner = CliRunner()


@pytest.fixture
def mock_deps():
    with (
        patch("coreason_git_automator.cli.AutomationConfig") as mock_config,
        patch("coreason_git_automator.cli.JulesWrapper") as mock_jules,
        patch("coreason_git_automator.cli.GitHubService") as mock_github,
        patch("coreason_git_automator.cli.DeepSeekClient") as mock_deepseek,
        patch("coreason_git_automator.cli.GitClient") as mock_git,
        patch("coreason_git_automator.cli.time.sleep") as mock_sleep,
    ):  # Mock sleep
        # Setup successful flow
        mock_jules_instance = mock_jules.return_value
        mock_jules_instance.verify_version.return_value = "1.0.0"

        mock_github_instance = mock_github.return_value
        mock_github_instance.verify_installed.return_value = "gh version 2.40.0"
        # Success on first try
        # Note: We need a recent timestamp for strict stale check
        recent_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        mock_github_instance.get_latest_run_status.return_value = {
            "status": "completed",
            "conclusion": "success",
            "databaseId": 123,
            "createdAt": recent_time,
        }
        mock_github_instance.create_pr.return_value = "http://pr.url"

        mock_deepseek_instance = mock_deepseek.return_value
        mock_deepseek_instance.generate_commit_info.return_value = DeepSeekCommit(
            commit_title="feat: thing", commit_body="- detail", branch_name="feat/thing"
        )

        mock_git_instance = mock_git.return_value
        mock_git_instance.get_log_oneline.return_value = "commit1\ncommit2"

        yield {
            "config": mock_config,
            "jules": mock_jules_instance,
            "github": mock_github_instance,
            "deepseek": mock_deepseek_instance,
            "git": mock_git_instance,
            "sleep": mock_sleep,
            "GitClientClass": mock_git,
        }


def test_help(mock_deps):
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "PROMPT" in result.stdout


def test_start_success(mock_deps):
    # Pass prompt as single word to avoid parsing issues if any
    result = runner.invoke(app, ["start", "Task", "--auto-fix"])

    assert result.exit_code == 0
    assert "Found Jules version" in result.stdout
    assert "Found GitHub CLI version" in result.stdout
    assert "PR Created" in result.stdout

    mock_deps["jules"].run_session.assert_called()


def test_start_repo_argument(mock_deps):
    # Verify --repo is passed to GitClient
    result = runner.invoke(app, ["start", "Task", "--repo", "/custom/repo"])
    assert result.exit_code == 0
    mock_deps["GitClientClass"].assert_called_with(repo_path="/custom/repo")


def test_start_stale_run_filtering(mock_deps):
    # Simulate old run, then new run
    old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    new_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    mock_deps["github"].get_latest_run_status.side_effect = [
        {"status": "completed", "conclusion": "success", "databaseId": 111, "createdAt": old_time},
        {"status": "completed", "conclusion": "success", "databaseId": 222, "createdAt": new_time},
    ]

    result = runner.invoke(app, ["start", "Task"])

    assert result.exit_code == 0
    # Should have skipped the first one
    # We can check if sleep was called (waiting for new run)
    assert mock_deps["sleep"].call_count >= 1


def test_start_missing_gh_cli(mock_deps):
    mock_deps["github"].verify_installed.side_effect = RuntimeError("GitHub CLI not found")

    result = runner.invoke(app, ["start", "Task"])

    assert result.exit_code == 1
    assert "Error: GitHub CLI not found" in result.stdout


def test_start_fail_then_success(mock_deps):
    # Mock failure then success
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()

    mock_deps["github"].get_latest_run_status.side_effect = [
        {"status": "completed", "conclusion": "failure", "databaseId": 123, "createdAt": future_time},
        {"status": "completed", "conclusion": "success", "databaseId": 124, "createdAt": future_time},
    ]
    mock_deps["github"].get_run_logs.return_value = "Log line\n" * 60

    result = runner.invoke(app, ["start", "Task", "--auto-fix"])

    assert result.exit_code == 0
    assert "CI failed" in result.stdout
    assert "Sending feedback" in result.stdout
    assert "CI passed" in result.stdout

    mock_deps["jules"].send_feedback.assert_called_once()


def test_start_fail_repeat_then_success(mock_deps):
    # Mock failure, then same failure (should wait), then success
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()

    mock_deps["github"].get_latest_run_status.side_effect = [
        {"status": "completed", "conclusion": "failure", "databaseId": 123, "createdAt": future_time},
        {"status": "completed", "conclusion": "failure", "databaseId": 123, "createdAt": future_time},  # Same run
        {"status": "completed", "conclusion": "success", "databaseId": 124, "createdAt": future_time},
    ]
    mock_deps["github"].get_run_logs.return_value = "Log line\n" * 60

    result = runner.invoke(app, ["start", "Task", "--auto-fix"])

    assert result.exit_code == 0

    # Should only call send_feedback once
    mock_deps["jules"].send_feedback.assert_called_once()


def test_start_wait_states(mock_deps):
    # Mock None (not started), Queued, In Progress, Success
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()

    mock_deps["github"].get_latest_run_status.side_effect = [
        None,
        {"status": "queued", "conclusion": None, "databaseId": 123, "createdAt": future_time},
        {"status": "in_progress", "conclusion": None, "databaseId": 123, "createdAt": future_time},
        {"status": "completed", "conclusion": "success", "databaseId": 123, "createdAt": future_time},
    ]

    result = runner.invoke(app, ["start", "Task", "--auto-fix"])

    assert result.exit_code == 0
    assert "CI passed" in result.stdout
    # Verify we waited
    assert mock_deps["sleep"].call_count >= 3


def test_start_exception(mock_deps):
    mock_deps["jules"].run_session.side_effect = RuntimeError("Fail")

    result = runner.invoke(app, ["start", "Task"])

    assert result.exit_code == 1
    assert "Error: Fail" in result.stdout


def test_start_git_conflict(mock_deps):
    # Simulate git merge conflict
    mock_deps["git"].merge_squash.side_effect = RuntimeError("Merge conflict")

    result = runner.invoke(app, ["start", "Task", "--auto-fix"])

    assert result.exit_code == 1
    assert "Git operation failed" in result.stdout
    assert "Merge Conflict" in result.stdout


def test_start_invalid_timestamp(mock_deps):
    # Mock invalid timestamp from GitHub
    mock_deps["github"].get_latest_run_status.return_value = {
        "status": "completed",
        "conclusion": "success",
        "databaseId": 123,
        "createdAt": "invalid-time-format",
    }

    result = runner.invoke(app, ["start", "Task", "--auto-fix"])

    assert result.exit_code == 0
    # Should proceed despite invalid timestamp (treated as relevant or error ignored)
    assert "CI passed" in result.stdout
