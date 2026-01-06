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
from tenacity import RetryError

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.github import GitHubService


@pytest.fixture
def mock_config(monkeypatch):
    """Mocks the AutomationConfig."""
    monkeypatch.setenv("JULES_API_KEY", "secret_jules")
    monkeypatch.setenv("GITHUB_TOKEN", "secret_gh")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret_ds")
    return AutomationConfig()


@pytest.fixture
def deepseek_client(mock_config):
    return DeepSeekClient(mock_config)


@pytest.fixture
def github_service():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        return GitHubService()


# --- DeepSeekClient Edge Cases ---


def test_deepseek_refusal(deepseek_client):
    """
    Complex Case: DeepSeek refuses to output JSON (e.g. returns plain text explanation).
    The client should retry (because of JSONDecodeError or similar) and eventually fail if it persists.
    """
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "I cannot provide JSON for this request because..."  # Not JSON
                }
            }
        ]
    }
    with patch("httpx.Client.post") as mock_post:
        # Mock success status but bad content
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("git log")


def test_deepseek_empty_response_body(deepseek_client):
    """
    Edge Case: API returns empty JSON body or unexpected structure.
    """
    mock_response = {}  # completely empty
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("git log")


def test_deepseek_partial_json(deepseek_client):
    """
    Edge Case: Valid JSON but missing one field.
    """
    mock_content = {
        "commit_title": "feat: missing others"
        # missing body and branch
    }
    mock_response = {"choices": [{"message": {"content": str(mock_content).replace("'", '"')}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("git log")


def test_deepseek_malformed_json_string(deepseek_client):
    """
    Edge Case: The 'content' string inside the JSON response is not valid JSON.
    """
    mock_response = {
        "choices": [{"message": {"content": "{ 'bad': json "}}]  # Missing closing brace/quote
    }
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("git log")


def test_deepseek_invalid_branch_name(deepseek_client):
    """
    Edge Case: API returns valid JSON structure, but branch name violates regex pattern.
    The spec requires pattern r"^[a-z0-9/-]+$".
    """
    mock_content = {
        "commit_title": "feat: valid",
        "commit_body": "- valid",
        "branch_name": "Invalid Branch Name!",  # Spaces and uppercase
    }
    mock_response = {"choices": [{"message": {"content": json.dumps(mock_content)}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError) as excinfo:
                deepseek_client.generate_commit_info("git log")

    # Check that validation error was the cause
    # Tenacity wraps the exception in RetryError
    # We need to access the underlying exception from the last attempt
    last_exception = excinfo.value.last_attempt.exception()
    assert last_exception is not None
    assert "Failed to parse DeepSeek response" in str(last_exception) or "Unexpected error" in str(last_exception)


# --- GitHubService Edge Cases ---


def test_github_unexpected_json_structure(github_service):
    """
    Edge Case: `gh api` returns a JSON object that is not the expected structure (missing workflow_runs).
    """
    with patch("subprocess.run") as mock_run:
        # Return a valid dict but missing "workflow_runs"
        mock_run.return_value = MagicMock(stdout='{"not": "expected"}', returncode=0)

        # get_latest_run_status expects {"workflow_runs": ...}
        status = github_service.get_latest_run_status("branch")
        assert status is None


def test_github_list_of_empty_objects(github_service):
    """
    Edge Case: `gh api` returns workflow_runs as empty objects.
    """
    with patch("subprocess.run") as mock_run:
        # workflow_runs is a list of empty dicts
        mock_run.return_value = MagicMock(stdout='{"workflow_runs": [{}, {}]}', returncode=0)

        status = github_service.get_latest_run_status("branch")
        # Should return the first dict, but with databaseId mapped from id (which is missing)
        # It calls `run.get("id")` -> None.
        assert status == {"databaseId": None}


def test_github_logs_unicode(github_service):
    """
    Edge Case: Logs contain unicode characters.
    """
    unicode_log = "Error: 🐛 in code\nFix it! 🚀"
    mock_jobs_response = {"jobs": [{"id": 999, "conclusion": "failure"}]}

    with patch("subprocess.run") as mock_run:
        # We need to mock 2 calls: one for jobs, one for logs
        def side_effect(args, **kwargs):
            # Check logs FIRST because URL contains "jobs" too
            if "logs" in args[2]:
                return MagicMock(stdout=unicode_log, returncode=0)
            if "jobs" in args[2]:  # crude check for endpoint
                return MagicMock(stdout=json.dumps(mock_jobs_response), returncode=0)
            return MagicMock(stdout="", returncode=0)

        mock_run.side_effect = side_effect

        logs = github_service.get_run_logs("123")
        assert "🐛" in logs
        assert "🚀" in logs
