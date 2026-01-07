# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from coreason_git_automator.utils.logger import configure_logging, logger


def test_configure_logging(tmp_path, monkeypatch):
    """
    Test that configure_logging sets up handlers and creates files.
    Uses monkeypatch.chdir to run in a temp dir, avoiding Path mocking issues.
    """
    # Run in tmp_path so "logs" directory is created there
    monkeypatch.chdir(tmp_path)

    configure_logging()

    # Verify directory and file creation
    log_dir = tmp_path / "logs"
    assert log_dir.exists()
    assert log_dir.is_dir()

    log_file = log_dir / "coreason_automator.log"
    # Note: Loguru might lazy-create the file, or create it immediately.
    # Let's log something to ensure it's flushed.
    logger.debug("Test audit log")

    # Flush logs by removing handlers (forces flush and close)
    logger.remove()

    assert log_file.exists()

    content = log_file.read_text()
    assert "Test audit log" in content


def test_logger_exports():
    """Test that logger is exported."""
    assert logger is not None
