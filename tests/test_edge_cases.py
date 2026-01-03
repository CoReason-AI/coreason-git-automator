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

import httpx
import pytest
from tenacity import RetryError

from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.github import GitHubService
from coreason_git_automator.services.jules import JulesWrapper


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.deepseek_api_key.get_secret_value.return_value = "test-key"
    return config


@pytest.fixture
def deepseek_client(mock_config):
    return DeepSeekClient(mock_config)


@pytest.fixture
def jules_wrapper():
    with patch("shutil.which", return_value="/usr/bin/jules"):
        return JulesWrapper()


@pytest.fixture
def github_service():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        return GitHubService()


# --- JulesWrapper Edge Cases ---


def test_jules_prepare_prompt_binary_file(jules_wrapper, tmp_path):
    """
    Edge Case: Context file contains binary data (or non-utf8).
    Should gracefully skip or handle error without crashing.
    """
    binary_file = tmp_path / "image.png"
    binary_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    # In strict implementation, reading binary as text raises UnicodeDecodeError
    # The current implementation catches 'Exception', so it should just log warning and continue.
    prompt = jules_wrapper._prepare_prompt("Task", [binary_file])

    # Should contain instruction but NOT the binary garbage
    assert "[INSTRUCTION]" in prompt
    assert "Task" in prompt
    # The current implementation logs warning on read failure, so prompt should not have [CONTEXT: ...] for this file
    assert f"[CONTEXT: {binary_file}]" not in prompt


def test_jules_prepare_prompt_missing_file(jules_wrapper, tmp_path):
    """
    Edge Case: Context file does not exist.
    """
    missing_file = tmp_path / "does_not_exist.py"
    prompt = jules_wrapper._prepare_prompt("Task", [missing_file])
    assert "[CONTEXT:" not in prompt
    assert "[INSTRUCTION]" in prompt


def test_jules_prepare_prompt_directory(jules_wrapper, tmp_path):
    """
    Edge Case: Context path is a directory.
    """
    dir_path = tmp_path / "somedir"
    dir_path.mkdir()
    prompt = jules_wrapper._prepare_prompt("Task", [dir_path])
    assert "[CONTEXT:" not in prompt
    assert "[INSTRUCTION]" in prompt


def test_jules_run_session_large_input(jules_wrapper):
    """
    Edge Case: extremely large prompt.
    Subprocess might have limits, but we are testing that we pass it correctly.
    """
    large_prompt = "A" * 100_000
    with patch("subprocess.run") as mock_run:
        jules_wrapper.run_session(large_prompt)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        # Verify the huge string is passed as last arg
        assert len(args[-1]) >= 100_000


# --- DeepSeekClient Edge Cases ---


def test_deepseek_rate_limit_retry(deepseek_client):
    """
    Edge Case: HTTP 429 Too Many Requests.
    Should retry according to tenacity config.
    """
    with patch("httpx.Client.post") as mock_post:
        # Simulate 429 response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        # Mock sleep to avoid waiting in tests
        with patch("tenacity.nap.time.sleep", return_value=None):
            # It should retry 3 times then raise RetryError
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("git log")

        # Verify multiple calls were made
        assert mock_post.call_count >= 3


def test_deepseek_empty_response(deepseek_client):
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
    Edge Case: `gh run list` returns a JSON object instead of a list.
    """
    with patch("subprocess.run") as mock_run:
        # Return a dict (object) instead of list
        mock_run.return_value = MagicMock(stdout='{"not": "a list"}', returncode=0)

        # get_latest_run_status expects list
        status = github_service.get_latest_run_status("branch")
        assert status is None


def test_github_list_of_empty_objects(github_service):
    """
    Edge Case: `gh run list` returns a list of empty objects.
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="[{}, {}]", returncode=0)

        status = github_service.get_latest_run_status("branch")
        # Should return the first empty dict
        assert status == {}


def test_github_logs_unicode(github_service):
    """
    Edge Case: Logs contain unicode characters.
    """
    unicode_log = "Error: 🐛 in code\nFix it! 🚀"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=unicode_log, returncode=0)

        logs = github_service.get_run_logs("123")
        assert "🐛" in logs
        assert "🚀" in logs
