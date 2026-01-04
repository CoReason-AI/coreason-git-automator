# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from unittest.mock import MagicMock, patch

import pytest
from tenacity import RetryError
from typer.testing import CliRunner

from coreason_git_automator.cli import app
from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.github import GitHubService

runner = CliRunner()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.deepseek_api_key.get_secret_value.return_value = "test-key"
    return config


@pytest.fixture
def deepseek_client(mock_config):
    return DeepSeekClient(mock_config)


@pytest.fixture
def github_service():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        return GitHubService()


def test_deepseek_refusal_plain_text(deepseek_client):
    """
    Complex Case: LLM ignores JSON mode and returns plain text refusal.
    This should raise a RuntimeError (wrapped in RetryError by tenacity).
    """
    mock_response = {
        "choices": [
            {"message": {"content": "I apologize, but I cannot fulfill this request as it involves modifying code."}}
        ]
    }

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError) as excinfo:
                deepseek_client.generate_commit_info("git log")

            # Verify specific error type
            assert "Failed to parse DeepSeek response" in str(excinfo.value.last_attempt.exception())


def test_github_auth_failure_text_response(github_service):
    """
    Complex Case: GitHub CLI is installed but not authenticated.
    It returns plain text 'Welcome to GitHub CLI' instead of JSON.
    """
    auth_error_text = "Welcome to GitHub CLI!\nTo get started, run: gh auth login"

    with patch("subprocess.run") as mock_run:
        # Simulate successful exit code (0) but non-JSON output (stdout)
        mock_run.return_value = MagicMock(stdout=auth_error_text, returncode=0)

        # We mock sleep to avoid waiting during retries
        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError) as excinfo:
                github_service.get_latest_run_status("branch")

        # Verify underlying exception
        assert "Failed to parse GitHub CLI output" in str(excinfo.value.last_attempt.exception())


def test_cli_empty_sanitized_log(mock_config):
    """
    Integration Case: Git log contains only filtered lines (jules/Co-authored-by).
    Sanitized log becomes empty.
    The CLI should handle this gracefully by aborting before calling DeepSeek.
    """
    with (
        patch("shutil.which", side_effect=lambda x: f"/usr/bin/{x}"),
        patch("coreason_git_automator.services.jules.JulesWrapper.verify_version"),
        patch("coreason_git_automator.services.github.GitHubService.verify_installed"),
        patch("coreason_git_automator.services.jules.JulesWrapper.run_session"),
        patch("coreason_git_automator.services.github.GitHubService.get_latest_run_status") as mock_status,
        patch("coreason_git_automator.services.git.GitClient.get_log_oneline") as mock_git_log,
        patch("coreason_git_automator.services.git.GitClient.checkout"),
        patch("coreason_git_automator.services.git.GitClient.pull"),
        # We Mock DeepSeek to ensure it is NOT called
        patch("coreason_git_automator.services.ai.DeepSeekClient.generate_commit_info") as mock_generate,
        patch("coreason_git_automator.cli.AutomationConfig", return_value=mock_config),
    ):
        # CI Success to reach Merge Step
        mock_status.return_value = {"status": "completed", "conclusion": "success", "databaseId": 123}

        # Git log only has dirty lines
        mock_git_log.return_value = "hash1 jules: update\nhash2 Co-authored-by: user"

        # Run CLI
        result = runner.invoke(app, ["start", "Task"])

        # Assertions
        # Expect failure because we haven't implemented the check yet, but let's see current behavior.
        # Current behavior: it calls generate_commit_info with empty string.
        # We WANT it to NOT call it and exit with error.

        # This test will initially FAIL (mock_generate called) or PASS (if we asserted mock_generate.called).
        # We want to assert behavior: abort.

        assert result.exit_code == 1
        assert "Empty git log after sanitization" in result.stdout
        mock_generate.assert_not_called()
