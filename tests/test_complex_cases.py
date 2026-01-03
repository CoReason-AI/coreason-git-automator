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

from coreason_git_automator.services.ai import DeepSeekClient

# --- DeepSeek Complex Cases ---


def test_deepseek_markdown_stripping():
    """
    Complex Case: API returns JSON wrapped in markdown code blocks.
    The client should strip them and parse the JSON.
    """
    mock_config = MagicMock()
    mock_config.deepseek_api_key.get_secret_value.return_value = "key"
    client = DeepSeekClient(mock_config)

    # Response with markdown
    json_content = json.dumps(
        {
            "commit_title": "feat: markdown",
            "commit_body": "- handled",
            "branch_name": "feat/markdown-strip",
        }
    )
    raw_content = f"```json\n{json_content}\n```"

    mock_response = {"choices": [{"message": {"content": raw_content}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        result = client.generate_commit_info("log")
        assert result.branch_name == "feat/markdown-strip"


def test_deepseek_plain_code_block_stripping():
    """
    Complex Case: API returns content wrapped in ``` but without 'json'.
    """
    mock_config = MagicMock()
    mock_config.deepseek_api_key.get_secret_value.return_value = "key"
    client = DeepSeekClient(mock_config)

    json_content = json.dumps(
        {
            "commit_title": "feat: plain block",
            "commit_body": "- handled",
            "branch_name": "feat/plain-block",
        }
    )
    raw_content = f"```\n{json_content}\n```"

    mock_response = {"choices": [{"message": {"content": raw_content}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        result = client.generate_commit_info("log")
        assert result.branch_name == "feat/plain-block"


def test_deepseek_empty_fields():
    """
    Complex Case: Valid JSON but fields are empty strings.
    """
    mock_config = MagicMock()
    mock_config.deepseek_api_key.get_secret_value.return_value = "key"
    client = DeepSeekClient(mock_config)

    mock_content = {
        "commit_title": "fix: empty body",
        "commit_body": "",  # Empty body allowed?
        "branch_name": "fix/empty-body",
    }
    mock_response = {"choices": [{"message": {"content": json.dumps(mock_content)}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        result = client.generate_commit_info("log")
        assert result.commit_body == ""
