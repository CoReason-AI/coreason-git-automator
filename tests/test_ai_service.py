import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from tenacity import RetryError

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.models import DeepSeekCommit
from coreason_git_automator.services.ai import DeepSeekClient


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AutomationConfig)
    config.deepseek_api_key = SecretStr("fake-key")
    return config


@pytest.fixture
def client(mock_config):
    return DeepSeekClient(mock_config)


def test_generate_commit_info_success(client):
    """Test successful generation of commit info with clean JSON."""
    mock_response_data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"commit_title": "feat: test", "commit_body": "- test body", "branch_name": "feat/test-branch"}
                    )
                }
            }
        ]
    }

    with patch("httpx.Client") as MockClient:
        mock_instance = MockClient.return_value.__enter__.return_value
        mock_instance.post.return_value.json.return_value = mock_response_data
        mock_instance.post.return_value.raise_for_status.return_value = None

        result = client.generate_commit_info("git log content")

        assert isinstance(result, DeepSeekCommit)
        assert result.commit_title == "feat: test"
        assert result.branch_name == "feat/test-branch"


def test_generate_commit_info_markdown_strip(client):
    """Test that markdown code blocks are stripped."""
    content_with_markdown = """
    Here is the JSON:
    ```json
    {
        "commit_title": "fix: bug",
        "commit_body": "- fixed it",
        "branch_name": "fix/bug-fix"
    }
    ```
    """
    mock_response_data = {"choices": [{"message": {"content": content_with_markdown}}]}

    with patch("httpx.Client") as MockClient:
        mock_instance = MockClient.return_value.__enter__.return_value
        mock_instance.post.return_value.json.return_value = mock_response_data

        result = client.generate_commit_info("git log")

        assert result.commit_title == "fix: bug"
        assert result.branch_name == "fix/bug-fix"


def test_generate_commit_info_dirty_json_extraction(client):
    """Test extracting JSON from conversational text."""
    content_dirty = """
    Sure, here is the JSON you requested:
    {
        "commit_title": "chore: cleanup",
        "commit_body": "- cleaned up",
        "branch_name": "chore/cleanup"
    }
    Hope this helps!
    """
    mock_response_data = {"choices": [{"message": {"content": content_dirty}}]}

    with patch("httpx.Client") as MockClient:
        mock_instance = MockClient.return_value.__enter__.return_value
        mock_instance.post.return_value.json.return_value = mock_response_data

        result = client.generate_commit_info("git log")

        assert result.commit_title == "chore: cleanup"


def test_generate_commit_info_api_error(client):
    """Test handling of API errors."""
    import httpx

    with patch("httpx.Client") as MockClient:
        mock_instance = MockClient.return_value.__enter__.return_value
        mock_instance.post.side_effect = httpx.HTTPError("API Error")

        with pytest.raises(RetryError) as excinfo:
            client.generate_commit_info("git log")

        assert isinstance(excinfo.value.last_attempt.exception(), RuntimeError)
        assert "DeepSeek API error" in str(excinfo.value.last_attempt.exception())


def test_generate_commit_info_parse_error(client):
    """Test handling of invalid JSON response."""
    mock_response_data = {"choices": [{"message": {"content": "Not JSON"}}]}

    with patch("httpx.Client") as MockClient:
        mock_instance = MockClient.return_value.__enter__.return_value
        mock_instance.post.return_value.json.return_value = mock_response_data

        with pytest.raises(RetryError) as excinfo:
            client.generate_commit_info("git log")

        assert isinstance(excinfo.value.last_attempt.exception(), RuntimeError)
        assert "Failed to parse DeepSeek response" in str(excinfo.value.last_attempt.exception())


def test_generate_commit_info_unexpected_error(client):
    """Test handling of unexpected generic exceptions."""
    with patch("httpx.Client") as MockClient:
        # Simulate an unexpected error (not httpx.HTTPError)
        MockClient.side_effect = Exception("Catastrophic failure")

        with pytest.raises(RetryError) as excinfo:
            client.generate_commit_info("git log")

        assert isinstance(excinfo.value.last_attempt.exception(), RuntimeError)
        assert "Unexpected error in DeepSeek client" in str(excinfo.value.last_attempt.exception())
