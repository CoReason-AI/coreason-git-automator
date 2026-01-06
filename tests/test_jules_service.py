import subprocess
from unittest.mock import patch

import pytest

from coreason_git_automator.services.jules import JulesWrapper


@pytest.fixture
def mock_shutil_which():
    with patch("shutil.which", return_value="/usr/bin/jules") as mock:
        yield mock


@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock:
        # Default behavior: success, return empty stdout
        mock.return_value.stdout = ""
        mock.return_value.returncode = 0
        yield mock


@pytest.fixture
def jules(mock_shutil_which):
    return JulesWrapper()


def test_init_raises_if_not_found():
    """Test that RuntimeError is raised if jules is not in PATH."""
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="Executable 'jules' not found"):
            JulesWrapper()


def test_verify_installed(jules, mock_subprocess_run):
    """Test version verification."""
    mock_subprocess_run.return_value.stdout = "jules version 1.0.0"
    version = jules.verify_installed()
    assert version == "jules version 1.0.0"

    # Check that subprocess.run was called correctly
    args = mock_subprocess_run.call_args[0][0]
    assert args == ["/usr/bin/jules", "--version"]


def test_verify_installed_failure(jules, mock_subprocess_run):
    """Test version verification failure."""
    # Simulate CalledProcessError
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["jules"], stderr="Error")

    with pytest.raises(RuntimeError):
        jules.verify_installed()


def test_run_session_no_context(jules, mock_subprocess_run):
    """Test starting a session without context files."""
    jules.run_session("Do something")

    args = mock_subprocess_run.call_args[0][0]
    assert args[0] == "/usr/bin/jules"
    assert args[1] == "remote"
    assert args[2] == "new"
    # Expect raw prompt since no context
    assert args[3] == "Do something"


def test_run_session_with_context(jules, mock_subprocess_run, tmp_path):
    """Test starting a session with context files."""
    # Create a dummy file
    f = tmp_path / "test.py"
    f.write_text("print('hello')")

    jules.run_session("Refactor this", context_files=[f])

    args = mock_subprocess_run.call_args[0][0]
    prompt_sent = args[3]

    # Check that context is prepended
    assert f"[CONTEXT: {f}]" in prompt_sent
    assert "print('hello')" in prompt_sent
    assert "[INSTRUCTION]" in prompt_sent
    assert "Refactor this" in prompt_sent


def test_run_session_context_read_error(jules, mock_subprocess_run, tmp_path):
    """Test that unreadable files are skipped gracefully."""
    # Create a directory instead of a file (reading it will fail)
    d = tmp_path / "somedir"
    d.mkdir()

    jules.run_session("Refactor this", context_files=[d])

    args = mock_subprocess_run.call_args[0][0]
    prompt_sent = args[3]

    # Should not contain context for the dir, but should still run
    assert "somedir" not in prompt_sent
    # It will contain [INSTRUCTION] because the list was not empty,
    # but the loop skipped the only item.
    # Wait, the logic is:
    # for file_path in context_files: ... context_str += ...
    # return f"{context_str}" + JULES_INSTRUCTION_HEADER...
    # So if list is not empty, header is added.
    assert "[INSTRUCTION]" in prompt_sent


def test_run_session_binary_file_skip(jules, mock_subprocess_run, tmp_path):
    """Test that binary files are skipped (UnicodeDecodeError)."""
    f = tmp_path / "image.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n")  # Binary data

    jules.run_session("Analyze this", context_files=[f])

    args = mock_subprocess_run.call_args[0][0]
    prompt_sent = args[3]

    # Should verify that the binary content is NOT in the prompt
    assert f"[CONTEXT: {f}]" not in prompt_sent


def test_run_session_failure(jules, mock_subprocess_run):
    """Test handling of session start failure."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["cmd"], stderr="fail")
    with pytest.raises(RuntimeError):
        jules.run_session("prompt")


def test_send_feedback(jules, mock_subprocess_run):
    """Test sending feedback."""
    jules.send_feedback("Error details")

    args = mock_subprocess_run.call_args[0][0]
    assert args[0] == "/usr/bin/jules"
    assert args[1] == "remote"
    assert args[2] == "chat"
    assert "Fix the code based on these errors" in args[3]
    assert "Error details" in args[3]


def test_send_feedback_failure(jules, mock_subprocess_run):
    """Test feedback failure."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["cmd"], stderr="fail")
    with pytest.raises(RuntimeError):
        jules.send_feedback("errors")
