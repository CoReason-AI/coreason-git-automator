# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from unittest.mock import MagicMock

import pytest

from coreason_git_automator.models import AutomationConfig, DeepSeekCommit
from coreason_git_automator.services.workflow import WorkflowOrchestrator


@pytest.fixture
def mock_components():
    config = MagicMock(spec=AutomationConfig)
    jules = MagicMock()
    github = MagicMock()
    deepseek = MagicMock()
    git = MagicMock()
    console = MagicMock()
    # Mock status context manager
    console.status.return_value.__enter__.return_value = MagicMock()

    # Default verifications
    jules.verify_installed.return_value = "1.0.0"
    github.verify_installed.return_value = "2.0.0"

    # Default git log
    git.get_log_oneline.return_value = "hash commit"

    # Default DeepSeek response
    deepseek.generate_commit_info.return_value = DeepSeekCommit(
        commit_title="feat: done", commit_body="- things", branch_name="feat/done"
    )

    return {"config": config, "jules": jules, "github": github, "deepseek": deepseek, "git": git, "console": console}


@pytest.fixture
def orchestrator(mock_components):
    return WorkflowOrchestrator(
        mock_components["config"],
        mock_components["jules"],
        mock_components["github"],
        mock_components["deepseek"],
        mock_components["git"],
        mock_components["console"],
    )


def test_workflow_zero_retries_fail(orchestrator, mock_components):
    """
    Test with max_retries=0.
    Should run once. If fails, it should abort immediately without trying to fix.
    Wait, 'auto-fix' implies we try to fix.
    If max_retries=0, does it mean "0 fixes allowed" or "0 extra retries"?
    Logic: stop_after_attempt(max_retries + 1).
    If max_retries=0, stop after 1 attempt.
    Attempt 1: Run -> Fail -> Raise RunFailedError.
    Tenacity checks stop condition: 1 attempt made. Stop? Yes.
    So it should raise RetryError (or RuntimeError as wrapped).
    And send feedback?
    Attempt 1 sends feedback BEFORE raising RunFailedError.
    So it sends feedback once, then aborts.
    """
    # Fail immediately
    mock_components["github"].get_latest_run_status.return_value = {
        "databaseId": 1,
        "status": "completed",
        "conclusion": "failure",
    }
    mock_components["github"].get_run_logs.return_value = "Error"

    with pytest.raises(RuntimeError, match="Max retries \(0\) exceeded"):
        orchestrator.start_session("p", None, "j", True, 0, "m")

    # Should have sent feedback once (during the single attempt)
    assert mock_components["jules"].send_feedback.call_count == 1


def test_workflow_zero_retries_success(orchestrator, mock_components):
    """
    Test with max_retries=0.
    Should run once. If success, all good.
    """
    mock_components["github"].get_latest_run_status.return_value = {
        "databaseId": 1,
        "status": "completed",
        "conclusion": "success",
    }

    orchestrator.start_session("p", None, "j", True, 0, "m")

    # Should succeed, merge, push
    mock_components["git"].push.assert_called()


def test_workflow_success_on_last_attempt(orchestrator, mock_components):
    """
    Test success exactly on the last allowed attempt.
    max_retries=2. Attempts allowed: 3.
    Sequence: Fail, Fail, Success.
    """
    mock_components["github"].get_run_logs.return_value = "Error"
    mock_components["github"].get_latest_run_status.side_effect = [
        {"databaseId": 1, "status": "completed", "conclusion": "failure"},  # Attempt 1
        {"databaseId": 2, "status": "completed", "conclusion": "failure"},  # Attempt 2
        {"databaseId": 3, "status": "completed", "conclusion": "success"},  # Attempt 3
    ]

    orchestrator.start_session("p", None, "j", True, 2, "m")

    # Should have succeeded
    mock_components["git"].push.assert_called()
    # Feedback calls: 2 (for the 2 failures)
    assert mock_components["jules"].send_feedback.call_count == 2


def test_workflow_multi_stage_failure(orchestrator, mock_components):
    """
    Test distinct failures in sequence to ensure state tracking works.
    Run 1 (Fail) -> Feedback -> Run 2 (Fail) -> Feedback -> Run 3 (Success).
    Crucially, verify that between Run 1 and Run 2, it waits for NEW run.
    """
    mock_components["github"].get_run_logs.return_value = "Error"

    # We need to simulate the polling behavior where it sees the OLD run first, then NEW run
    mock_components["github"].get_latest_run_status.side_effect = [
        # Attempt 1
        {"databaseId": 100, "status": "completed", "conclusion": "failure"},
        # Attempt 2 starts. It polls.
        # Suppose it sees ID 100 again (old run)
        {"databaseId": 100, "status": "completed", "conclusion": "failure"},
        # Then sees ID 200 (new run, failed)
        {"databaseId": 200, "status": "completed", "conclusion": "failure"},
        # Attempt 3 starts. Polls.
        # Sees ID 200 (old)
        {"databaseId": 200, "status": "completed", "conclusion": "failure"},
        # Sees ID 300 (new, success)
        {"databaseId": 300, "status": "completed", "conclusion": "success"},
    ]

    orchestrator.start_session("p", None, "j", True, 2, "m")

    assert mock_components["jules"].send_feedback.call_count == 2
    # Verify feedback was sent for correct runs?
    # We can't easily verify args here without capturing, but call count implies progression.
