# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import concurrent.futures
import json

from coreason_git_automator.utils.logger import configure_logging, logger


def test_logging_concurrency(tmp_path, monkeypatch):
    """
    Complex Case: Verify thread safety of the logging setup.
    Multiple threads should write to the log file without corruption.
    """
    monkeypatch.chdir(tmp_path)
    configure_logging()

    log_file = tmp_path / "logs" / "app.log"
    thread_count = 10
    logs_per_thread = 100

    def worker(thread_id):
        for i in range(logs_per_thread):
            logger.debug(f"Thread {thread_id} msg {i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = [executor.submit(worker, i) for i in range(thread_count)]
        concurrent.futures.wait(futures)

    # Force flush
    logger.remove()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    lines = content.strip().splitlines()

    # Verify total count
    assert len(lines) == thread_count * logs_per_thread

    # Verify every line is valid JSON
    for line in lines:
        try:
            data = json.loads(line)
            assert "text" in data
            assert "record" in data
        except json.JSONDecodeError as e:
            raise AssertionError(f"Corrupted JSON line: {line}") from e


def test_logging_special_characters(tmp_path, monkeypatch):
    """
    Edge Case: Verify handling of special characters and emojis in JSON logs.
    """
    monkeypatch.chdir(tmp_path)
    configure_logging()

    log_file = tmp_path / "logs" / "app.log"

    special_msg = "Hello \n World \" ' 🌍"
    logger.info(special_msg)

    logger.remove()

    content = log_file.read_text(encoding="utf-8")
    data = json.loads(content.strip())

    # Verify the raw message is preserved correctly
    assert data["record"]["message"] == special_msg


def test_reconfiguration(tmp_path, monkeypatch):
    """
    Edge Case: Verify that calling configure_logging multiple times
    does not duplicate handlers or corrupt state.
    """
    monkeypatch.chdir(tmp_path)

    # First configuration
    configure_logging()
    logger.info("First run")

    # Second configuration
    configure_logging()
    logger.info("Second run")

    logger.remove()

    log_file = tmp_path / "logs" / "app.log"
    content = log_file.read_text(encoding="utf-8")
    lines = content.strip().splitlines()

    # If handlers were duplicated, "Second run" might appear twice or cause issues
    assert len(lines) == 2
    assert "First run" in lines[0]
    assert "Second run" in lines[1]
