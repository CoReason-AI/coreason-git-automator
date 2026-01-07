# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import pytest
from pydantic import ValidationError

from coreason_git_automator.config import AutomationConfig


def test_config_valid_env():
    """Test configuration loading with valid environment variables."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("JULES_API_KEY", "test_jules_key")
        m.setenv("GITHUB_TOKEN", "test_github_token")
        m.setenv("DEEPSEEK_API_KEY", "test_deepseek_key")

        config = AutomationConfig()

        assert config.jules_api_key.get_secret_value() == "test_jules_key"
        assert config.github_token.get_secret_value() == "test_github_token"
        assert config.deepseek_api_key.get_secret_value() == "test_deepseek_key"


def test_config_missing_env():
    """Test configuration failure when environment variables are missing."""
    # Ensure env vars are unset
    with pytest.MonkeyPatch.context() as m:
        m.delenv("JULES_API_KEY", raising=False)
        m.delenv("GITHUB_TOKEN", raising=False)
        m.delenv("DEEPSEEK_API_KEY", raising=False)

        with pytest.raises(ValidationError):
            AutomationConfig()


def test_config_empty_env():
    """Test configuration failure when environment variables are empty strings."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("JULES_API_KEY", "")
        m.setenv("GITHUB_TOKEN", "")
        m.setenv("DEEPSEEK_API_KEY", "")

        with pytest.raises(ValidationError) as exc:
            AutomationConfig()

        errors = str(exc.value)
        assert "Secret cannot be empty" in errors
