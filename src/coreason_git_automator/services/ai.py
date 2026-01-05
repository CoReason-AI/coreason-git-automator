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
import re
from typing import Any

import httpx
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.models import DeepSeekCommit
from coreason_git_automator.utils.logger import logger


class DeepSeekClient:
    """
    Client for interacting with the DeepSeek API.
    """

    def __init__(self, config: AutomationConfig):
        self.api_key = config.deepseek_api_key.get_secret_value()
        self.base_url = "https://api.deepseek.com/v1"

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
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-coder",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": git_log},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]

                # Clean and parse JSON response
                parsed_content = self._clean_and_parse_json(content)

                return DeepSeekCommit(**parsed_content)

        except httpx.HTTPError as e:
            logger.error(f"DeepSeek API error: {e}")
            raise RuntimeError(f"DeepSeek API error: {e}") from e
        except (json.JSONDecodeError, KeyError, ValidationError) as e:
            logger.error(f"Failed to parse DeepSeek response: {e}")
            raise RuntimeError(f"Failed to parse DeepSeek response: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in DeepSeek client: {e}")
            raise RuntimeError(f"Unexpected error in DeepSeek client: {e}") from e

    def _clean_and_parse_json(self, content: str) -> dict[str, Any]:
        """
        Strips markdown code blocks and extracts JSON object if embedded in text.
        Returns parsed JSON dict.
        """
        # 1. Strip markdown code block delimiters
        content = re.sub(r"^```[a-zA-Z]*\n", "", content.strip())
        content = re.sub(r"\n```$", "", content.strip())
        content = content.strip("`")

        # 2. Try direct parse
        try:
            return dict(json.loads(content))
        except json.JSONDecodeError:
            # 3. Fallback: Extract first JSON object between braces
            logger.warning("Direct JSON parse failed. Attempting to extract JSON from text.")
            try:
                start_index = content.index("{")
                end_index = content.rindex("}") + 1
                json_str = content[start_index:end_index]
                return dict(json.loads(json_str))
            except (ValueError, json.JSONDecodeError) as e:
                # If extraction fails, raise original error context
                raise json.JSONDecodeError("Failed to extract valid JSON object", content, 0) from e
