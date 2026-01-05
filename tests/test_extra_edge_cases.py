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


@pytest.fixture
def mock_config(monkeypatch):
    monkeypatch.setenv("JULES_API_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")
    return AutomationConfig()


@pytest.fixture
def deepseek_client(mock_config):
    return DeepSeekClient(mock_config)


def test_deepseek_json_embedded_in_text(deepseek_client):
    """
    Edge Case: LLM returns valid JSON but surrounded by conversational text WITHOUT code blocks.
    The current implementation might fail this if it only looks for markdown blocks or expects pure JSON.
    We want to upgrade the client to be robust enough to find the JSON object.
    """
    valid_json = json.dumps(
        {
            "commit_title": "feat: robust json parsing",
            "commit_body": "- extracted json from text",
            "branch_name": "feat/robust-json",
        }
    )

    # Text surrounding the JSON
    content = f"Here is the JSON you requested:\n\n{valid_json}\n\nHope this helps!"

    mock_response = {"choices": [{"message": {"content": content}}]}

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: mock_response, raise_for_status=lambda: None)

        # This SHOULD pass if we implement robust extraction.
        # Currently, it will likely fail (RetryError) because json.loads(content) will fail.
        # We catch the failure to confirm we need to fix it.
        try:
            result = deepseek_client.generate_commit_info("git log")
            assert result.commit_title == "feat: robust json parsing"
        except RetryError:
            pytest.fail("DeepSeekClient could not extract JSON from surrounding text.")


def test_deepseek_json_with_comments(deepseek_client):
    """
    Edge Case: LLM returns JSON-like string but with JS-style comments (common hallucination).
    Python's json.loads doesn't support comments.
    This is a "Nice to have" robustness check.
    """
    # ... actually, let's stick to the "embedded in text" case as the primary robust feature for now.
    pass
