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

from coreason_git_automator.models import DeepSeekCommit
from coreason_git_automator.services.ai import DeepSeekClient


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.deepseek_api_key.get_secret_value.return_value = "test-key"
    return config


@pytest.fixture
def deepseek_client(mock_config):
    return DeepSeekClient(mock_config)


def test_generate_commit_info_success(deepseek_client):
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "commit_title": "feat: new feature",
                            "commit_body": "- Implemented feature",
                            "branch_name": "feat/new-feature",
                        }
                    )
                }
            }
        ]
    }

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        result = deepseek_client.generate_commit_info("raw log")

        assert isinstance(result, DeepSeekCommit)
        assert result.commit_title == "feat: new feature"
        assert result.branch_name == "feat/new-feature"


def test_generate_commit_info_http_error(deepseek_client):
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock())

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("raw log")


def test_generate_commit_info_strip_markdown(deepseek_client):
    """Verifies that markdown code blocks are stripped from the response."""
    dirty_json = """```json
    {
        "commit_title": "feat: stripped",
        "commit_body": "- handled markdown",
        "branch_name": "feat/stripped"
    }
    ```"""
    mock_response = {"choices": [{"message": {"content": dirty_json}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        result = deepseek_client.generate_commit_info("raw log")

        assert result.commit_title == "feat: stripped"


def test_generate_commit_info_parse_error(deepseek_client):
    mock_response = {"choices": [{"message": {"content": "Invalid JSON"}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("raw log")


def test_generate_commit_info_schema_error(deepseek_client):
    # Missing fields
    mock_response = {"choices": [{"message": {"content": json.dumps({"commit_title": "feat: incomplete"})}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                # Should fail validation and retry
                deepseek_client.generate_commit_info("raw log")


def test_generate_commit_info_unexpected_error(deepseek_client):
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = Exception("Unexpected")

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError):
                deepseek_client.generate_commit_info("raw log")
