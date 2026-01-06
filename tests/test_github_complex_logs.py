# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from unittest.mock import patch

import pytest

from coreason_git_automator.services.github import GitHubService


@pytest.fixture
def github_service():
    with patch("shutil.which", return_value="/usr/bin/gh"):
        yield GitHubService()


def test_jobs_response_jobs_not_list(github_service):
    """Test when 'jobs' key exists but value is not a list."""
    mock_response = {"jobs": "this is a string, not a list"}

    with patch.object(github_service, "_run_gh_command", return_value=mock_response):
        with pytest.raises(RuntimeError, match="Invalid jobs structure"):
            github_service.get_run_logs("123")


def test_jobs_list_contains_non_dicts(github_service):
    """Test when 'jobs' list contains non-dictionary items."""
    mock_response = {
        "jobs": [
            {"id": 1, "conclusion": "success"},
            "invalid_item",  # String instead of dict
            {"id": 2, "conclusion": "failure"},
        ]
    }

    with patch.object(github_service, "_run_gh_command", return_value=mock_response):
        with patch("coreason_git_automator.services.github.run_command") as mock_run_cmd:
            mock_run_cmd.return_value = "Log content"
            # Should skip invalid item and find the failure at id 2
            github_service.get_run_logs("123")

            # Verify it called logs for job 2
            assert "actions/jobs/2/logs" in mock_run_cmd.call_args[0][0][2]


def test_jobs_missing_conclusion_and_id(github_service):
    """Test when job objects are missing 'conclusion' or 'id' keys."""
    mock_response = {
        "jobs": [
            {"status": "completed"},  # Missing id and conclusion
            {"id": 3, "conclusion": "failure"},
        ]
    }

    with patch.object(github_service, "_run_gh_command", return_value=mock_response):
        with patch("coreason_git_automator.services.github.run_command") as mock_run_cmd:
            mock_run_cmd.return_value = "Log content"

            github_service.get_run_logs("123")

            # Should ignore the malformed job and pick the failed one
            assert "actions/jobs/3/logs" in mock_run_cmd.call_args[0][0][2]


def test_jobs_list_only_invalid_items(github_service):
    """Test when 'jobs' list contains only non-dictionary items."""
    mock_response = {"jobs": ["invalid", 123, None]}

    with patch.object(github_service, "_run_gh_command", return_value=mock_response):
        with pytest.raises(RuntimeError, match="No valid job objects found in response"):
            github_service.get_run_logs("123")
