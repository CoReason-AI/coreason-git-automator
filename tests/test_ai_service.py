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
from openai import APIError
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
    # Mock the OpenAI client creation
    with patch("coreason_git_automator.services.ai.OpenAI") as mock_openai:
        client = DeepSeekClient(mock_config)
        client.client = mock_openai.return_value  # Use the mock instance
        return client


def test_generate_commit_info_success(deepseek_client):
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "commit_title": "feat: new feature",
                        "commit_body": "- Implemented feature",
                        "branch_name": "feat/new-feature",
                    }
                )
            )
        )
    ]

    deepseek_client.client.chat.completions.create.return_value = mock_response

    result = deepseek_client.generate_commit_info("raw log")

    assert isinstance(result, DeepSeekCommit)
    assert result.commit_title == "feat: new feature"
    assert result.branch_name == "feat/new-feature"


def test_generate_commit_info_api_error(deepseek_client):
    deepseek_client.client.chat.completions.create.side_effect = APIError("API Error", request=MagicMock(), body={})

    with patch("tenacity.nap.time.sleep", return_value=None):
        with pytest.raises(RetryError):
            deepseek_client.generate_commit_info("raw log")


def test_generate_commit_info_parse_error(deepseek_client):
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Invalid JSON"))]
    deepseek_client.client.chat.completions.create.return_value = mock_response

    with patch("tenacity.nap.time.sleep", return_value=None):
        with pytest.raises(RetryError):
            deepseek_client.generate_commit_info("raw log")


def test_generate_commit_info_schema_error(deepseek_client):
    # Missing fields
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps({"commit_title": "feat: incomplete"})))]
    deepseek_client.client.chat.completions.create.return_value = mock_response

    with patch("tenacity.nap.time.sleep", return_value=None):
        with pytest.raises(RetryError):
            # Should fail validation and retry
            deepseek_client.generate_commit_info("raw log")


def test_generate_commit_info_unexpected_error(deepseek_client):
    deepseek_client.client.chat.completions.create.side_effect = Exception("Unexpected")

    with patch("tenacity.nap.time.sleep", return_value=None):
        with pytest.raises(RetryError):
            deepseek_client.generate_commit_info("raw log")
