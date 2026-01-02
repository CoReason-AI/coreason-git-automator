# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class AutomationConfig(BaseSettings):
    """
    Configuration for the Coreason Git Automator.
    Reads from environment variables.
    """

    jules_api_key: SecretStr = Field(alias="JULES_API_KEY")
    github_token: SecretStr = Field(alias="GITHUB_TOKEN")
    deepseek_api_key: SecretStr = Field(alias="DEEPSEEK_API_KEY")
