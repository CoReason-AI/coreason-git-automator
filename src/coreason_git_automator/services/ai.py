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

from openai import APIError, OpenAI
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.models import DeepSeekCommit
from coreason_git_automator.utils.logger import logger


class DeepSeekClient:
    """
    Client for interacting with the DeepSeek API via OpenAI SDK.
    """

    def __init__(self, config: AutomationConfig):
        self.client = OpenAI(
            api_key=config.deepseek_api_key.get_secret_value(),
            base_url="https://api.deepseek.com/v1",
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))  # type: ignore
    def generate_commit_info(self, git_log: str) -> DeepSeekCommit:
        """
        Analyzes the git log and generates a conventional commit message and branch name.
        """
        system_prompt = (
            "You are a Senior Release Engineer. Analyze the provided git commit log. "
            "Your goal is to consolidate the work into a single 'Conventional Commit' message "
            "and suggest a clean git branch name.\n"
            "Output purely valid JSON with no markdown formatting."
        )

        try:
            response = self.client.chat.completions.create(
                model="deepseek-coder",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": git_log},
                ],
                response_format={"type": "json_object"},
                timeout=30.0,
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Received empty content from DeepSeek API")

            if "```json" in content:
                content = content.replace("```json", "").replace("```", "")
            elif "```" in content:
                content = content.replace("```", "")

            parsed_content = json.loads(content.strip())
            return DeepSeekCommit(**parsed_content)

        except APIError as e:
            logger.error(f"DeepSeek API error: {e}")
            raise RuntimeError(f"DeepSeek API error: {e}") from e
        except (json.JSONDecodeError, KeyError, ValidationError, ValueError) as e:
            logger.error(f"Failed to parse DeepSeek response: {e}")
            raise RuntimeError(f"Failed to parse DeepSeek response: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in DeepSeek client: {e}")
            raise RuntimeError(f"Unexpected error in DeepSeek client: {e}") from e
