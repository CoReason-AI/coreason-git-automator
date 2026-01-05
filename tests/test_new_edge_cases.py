# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from tenacity import RetryError

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.github import GitHubService
from coreason_git_automator.services.jules import JulesWrapper


@pytest.fixture
def mock_config(monkeypatch):
    monkeypatch.setenv("JULES_API_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret")
    return AutomationConfig()


@pytest.fixture
def deepseek_client(mock_config):
    return DeepSeekClient(mock_config)


@pytest.fixture
def jules_wrapper():
    with patch("shutil.which", return_value="/bin/jules"):
        return JulesWrapper()


@pytest.fixture
def github_service():
    with patch("shutil.which", return_value="/bin/gh"):
        return GitHubService()


def test_deepseek_rate_limit(deepseek_client):
    """
    Edge Case: DeepSeek API returns 429 Rate Limit.
    Should retry and eventually raise RetryError.
    """
    with patch("httpx.Client.post") as mock_post:
        # Simulate 429
        mock_post.side_effect = httpx.HTTPStatusError(
            "Rate Limited", request=MagicMock(), response=MagicMock(status_code=429)
        )

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError) as excinfo:
                deepseek_client.generate_commit_info("log")

            # Verify the underlying error is HTTPStatusError or RuntimeError wrapping it
            # The DeepSeekClient catches HTTPError and raises RuntimeError
            exc = excinfo.value.last_attempt.exception()
            assert isinstance(exc, RuntimeError)
            assert "DeepSeek API error" in str(exc)


def test_jules_mixed_context_files(jules_wrapper, tmp_path):
    """
    Edge Case: One valid text file, one binary file.
    Should include valid content and skip binary without crashing.
    """
    # Valid file
    f_valid = tmp_path / "valid.txt"
    f_valid.write_text("valid content", encoding="utf-8")

    # Binary file (simulated with mock to ensure UnicodeDecodeError)
    f_binary = MagicMock(spec=Path)
    f_binary.__str__.return_value = "binary.bin"
    f_binary.read_text.side_effect = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")

    with patch("coreason_git_automator.services.jules.logger") as mock_logger:
        prompt = jules_wrapper._prepare_prompt("Prompt", [f_valid, f_binary])

        # Check valid content is there
        assert "[CONTEXT: " + str(f_valid) + "]" in prompt
        assert "valid content" in prompt

        # Check binary is missing
        assert "[CONTEXT: binary.bin]" not in prompt

        # Check warning logged
        mock_logger.warning.assert_called()


def test_jules_empty_context_file(jules_wrapper, tmp_path):
    """
    Edge Case: Empty context file.
    Should include the header but empty body.
    """
    f_empty = tmp_path / "empty.txt"
    f_empty.write_text("", encoding="utf-8")

    prompt = jules_wrapper._prepare_prompt("Prompt", [f_empty])

    assert f"[CONTEXT: {f_empty}]\n\n" in prompt


def test_github_auth_error_text(github_service):
    """
    Edge Case: `gh` returns text output (Auth error) instead of JSON.
    """
    with patch("subprocess.run") as mock_run:
        # gh often prints "Welcome to GitHub CLI" or "Re-authenticate" on stdout/stderr if auth fails
        mock_run.return_value = MagicMock(stdout="Welcome to GitHub CLI!\nPlease login.", returncode=0)

        with patch("tenacity.nap.time.sleep", return_value=None):
            # The service tries to json.loads this, fails, retries, and finally raises RetryError
            with pytest.raises(RetryError) as excinfo:
                github_service.get_latest_run_status("branch")

            exc = excinfo.value.last_attempt.exception()
            assert isinstance(exc, RuntimeError)
            assert "Failed to parse GitHub CLI output" in str(exc)


def test_github_network_error(github_service):
    """
    Edge Case: `subprocess.run` raises generic error (e.g. OOM or signal).
    """
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = RuntimeError("Subprocess failed")

        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(RetryError) as excinfo:
                github_service.get_latest_run_status("branch")

            exc = excinfo.value.last_attempt.exception()
            assert isinstance(exc, RuntimeError)
            assert "Subprocess failed" in str(exc)
