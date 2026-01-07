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

from coreason_git_automator.utils.logger import configure_logging, logger


def test_configure_logging(tmp_path, monkeypatch):
    """
    Test that configure_logging sets up handlers and creates files.
    Uses monkeypatch.chdir to run in a temp dir, avoiding Path mocking issues.
    Verifies JSON output and correct filename.
    """
    # Run in tmp_path so "logs" directory is created there
    monkeypatch.chdir(tmp_path)

    configure_logging()

    # Verify directory creation
    log_dir = tmp_path / "logs"
    assert log_dir.exists()
    assert log_dir.is_dir()

    # Target file should be app.log now
    log_file = log_dir / "app.log"

    # Log something to ensure it's flushed.
    test_message = "Test audit log JSON"
    logger.debug(test_message)

    # Flush logs by removing handlers (forces flush and close)
    logger.remove()

    assert log_file.exists()

    content = log_file.read_text()

    # Verify content contains the message
    assert test_message in content

    # Verify it is valid JSON
    # Loguru JSON output is one JSON object per line.
    lines = content.strip().splitlines()
    assert len(lines) > 0
    last_line = lines[-1]

    data = json.loads(last_line)

    # Verify the raw message is correct in the record
    assert data["record"]["message"] == test_message

    # Verify the level is correct
    assert data["record"]["level"]["name"] == "DEBUG"


def test_logger_exports():
    """Test that logger is exported."""
    assert logger is not None
