# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coreason_git_automator.services.jules import JulesWrapper


@pytest.fixture
def mock_shutil_which():
    with patch("shutil.which") as mock:
        mock.return_value = "/usr/bin/jules"
        yield mock


@pytest.fixture
def jules_wrapper(mock_shutil_which):
    return JulesWrapper()


def test_init_success(mock_shutil_which):
    jw = JulesWrapper()
    assert jw.executable == "/usr/bin/jules"


def test_init_not_found():
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="Jules executable 'jules' not found"):
            JulesWrapper()


def test_verify_version_success(jules_wrapper):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="1.0.0\n", returncode=0)

        version = jules_wrapper.verify_version()

        assert version == "1.0.0"
        mock_run.assert_called_once()


def test_verify_version_failure(jules_wrapper):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["jules"], stderr="Error")

        with pytest.raises(RuntimeError, match="Command failed"):
            jules_wrapper.verify_version()


def test_prepare_prompt_no_context(jules_wrapper):
    prompt = jules_wrapper._prepare_prompt("Do something", None)
    assert prompt == "Do something"


def test_prepare_prompt_with_context(jules_wrapper, tmp_path):
    f1 = tmp_path / "test.py"
    f1.write_text("print('hello')")

    prompt = jules_wrapper._prepare_prompt("Fix it", [f1])

    expected = f"[CONTEXT: {f1}]\nprint('hello')\n\n[INSTRUCTION]\nFix it"
    assert prompt == expected


def test_prepare_prompt_read_error(jules_wrapper):
    # Mock Path.read_text to raise exception
    f1 = MagicMock(spec=Path)
    f1.read_text.side_effect = Exception("Read error")
    f1.__str__.return_value = "file.py"

    prompt = jules_wrapper._prepare_prompt("Fix it", [f1])

    # Should skip the file content but still return prompt
    assert "[INSTRUCTION]" in prompt
    assert "Fix it" in prompt


def test_prepare_prompt_binary_file(jules_wrapper):
    """
    Complex Case: Binary file (UnicodeDecodeError) should be gracefully skipped.
    """
    f1 = MagicMock(spec=Path)
    # Simulate UnicodeDecodeError (which inherits from ValueError in Py3, but specifically checked in memory)
    # Memory: "JulesWrapper must explicitly use encoding='utf-8' when reading context files;
    # this ensures binary files raise UnicodeDecodeError and are skipped correctly."
    f1.read_text.side_effect = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
    f1.__str__.return_value = "binary.bin"

    with patch("coreason_git_automator.services.jules.logger") as mock_logger:
        prompt = jules_wrapper._prepare_prompt("Fix it", [f1])

        # Ensure we logged a warning
        mock_logger.warning.assert_called()
        assert "Failed to read context file" in mock_logger.warning.call_args[0][0]

    # Content should not be in prompt
    assert "[CONTEXT: binary.bin]" not in prompt
    assert "Fix it" in prompt


def test_run_session_success(jules_wrapper):
    with patch("subprocess.run") as mock_run:
        jules_wrapper.run_session("Prompt")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "remote" in args and "new" in args


def test_run_session_failure(jules_wrapper):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["jules"])

        with pytest.raises(RuntimeError, match="Command failed"):
            jules_wrapper.run_session("Prompt")


def test_send_feedback_success(jules_wrapper):
    with patch("subprocess.run") as mock_run:
        jules_wrapper.send_feedback("Errors found")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "remote" in args and "chat" in args
        assert "Errors found" in args[3]


def test_send_feedback_failure(jules_wrapper):
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["jules"])

        with pytest.raises(RuntimeError, match="Command failed"):
            jules_wrapper.send_feedback("Errors")
