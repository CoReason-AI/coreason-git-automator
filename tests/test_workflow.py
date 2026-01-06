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


def test_start_session_full_flow(orchestrator, mock_components):
    """Test the happy path of the session."""
    # Setup mocks
    mock_components["jules"].verify_installed.return_value = "1.0"
    mock_components["github"].verify_installed.return_value = "2.0"

    # Git
    mock_components["git"].get_log_oneline.return_value = "hash commit"

    # GitHub status (Success immediately)
    mock_components["github"].get_latest_run_status.return_value = {
        "databaseId": 1,
        "conclusion": "success",
        "status": "completed",
    }

    # DeepSeek
    commit_info = DeepSeekCommit(commit_title="feat: done", commit_body="- things", branch_name="feat/done")
    mock_components["deepseek"].generate_commit_info.return_value = commit_info

    # GitHub PR
    mock_components["github"].create_pr.return_value = "http://pr"

    # Run
    orchestrator.start_session("prompt", None, "jules-branch", True, 3, "main")

    # Verifications
    mock_components["jules"].run_session.assert_called_with("prompt", None)
    mock_components["github"].get_latest_run_status.assert_called()
    mock_components["git"].merge_squash.assert_called_with("jules-branch")
    mock_components["git"].push.assert_called_with("feat/done")
    mock_components["github"].create_pr.assert_called()


def test_monitor_ci_loop_waiting(orchestrator, mock_components):
    """Test that it waits when CI is queued/in_progress."""
    # 1. Queued, 2. In Progress, 3. Success
    statuses = [
        {"databaseId": 1, "status": "queued", "conclusion": None},
        {"databaseId": 1, "status": "in_progress", "conclusion": None},
        {"databaseId": 1, "status": "completed", "conclusion": "success"},
    ]
    mock_components["github"].get_latest_run_status.side_effect = statuses

    # DeepSeek setup to allow flow to finish
    mock_components["deepseek"].generate_commit_info.return_value = DeepSeekCommit(
        commit_title="t", commit_body="b", branch_name="b"
    )
    mock_components["git"].get_log_oneline.return_value = "log"

    orchestrator.start_session("p", None, "j", True, 3, "m")

    assert mock_components["github"].get_latest_run_status.call_count == 3


def test_monitor_ci_loop_failure_feedback(orchestrator, mock_components):
    """Test failure feedback loop."""
    # 1. Failure -> Send Feedback
    # 2. Success (after fix)

    # Note: Logic handles re-fetching status.
    # If failure detected, it fetches logs, sends feedback, increments failures.
    # Then it loops again.

    statuses = [
        {"databaseId": 1, "status": "completed", "conclusion": "failure"},
        {"databaseId": 2, "status": "completed", "conclusion": "success"},  # New run passed
    ]
    mock_components["github"].get_latest_run_status.side_effect = statuses
    mock_components["github"].get_run_logs.return_value = "Log line 1\n...\nError"

    # DeepSeek setup
    mock_components["deepseek"].generate_commit_info.return_value = DeepSeekCommit(
        commit_title="t", commit_body="b", branch_name="b"
    )
    mock_components["git"].get_log_oneline.return_value = "log"

    orchestrator.start_session("p", None, "j", True, 3, "m")

    # Verify feedback sent
    mock_components["jules"].send_feedback.assert_called_once()
    assert "Error" in mock_components["jules"].send_feedback.call_args[0][0]


def test_monitor_ci_loop_max_retries(orchestrator, mock_components):
    """Test max retries exceeded."""
    # Always fail
    fail_status = {"databaseId": 1, "status": "completed", "conclusion": "failure"}
    mock_components["github"].get_latest_run_status.return_value = fail_status
    mock_components["github"].get_run_logs.return_value = "Error"

    # Note: run_id needs to change to count as a new attempt?
    # Logic:
    # if conclusion == "failure":
    #    if run_id == last_processed_run_id: continue (wait for new run)
    #    else: feedback, failures++

    # So we need distinctive run IDs for each failure
    statuses = [
        {"databaseId": 1, "status": "completed", "conclusion": "failure"},
        {"databaseId": 2, "status": "completed", "conclusion": "failure"},
        {"databaseId": 3, "status": "completed", "conclusion": "failure"},
    ]
    mock_components["github"].get_latest_run_status.side_effect = statuses

    with pytest.raises(RuntimeError, match=r"Max retries \(2\) exceeded"):
        orchestrator.start_session("p", None, "j", True, 2, "m")


def test_monitor_ci_loop_no_runs_yet(orchestrator, mock_components):
    """Test waiting when no runs are returned initially."""
    statuses = [
        None,  # First poll returns None
        {"databaseId": 1, "status": "completed", "conclusion": "success"},  # Second poll success
    ]
    mock_components["github"].get_latest_run_status.side_effect = statuses

    mock_components["deepseek"].generate_commit_info.return_value = DeepSeekCommit(
        commit_title="t", commit_body="b", branch_name="b"
    )
    mock_components["git"].get_log_oneline.return_value = "log"

    orchestrator.start_session("p", None, "j", True, 3, "m")

    assert mock_components["github"].get_latest_run_status.call_count == 2


def test_sanitized_log_empty(orchestrator, mock_components):
    """Test abort if git log is empty after sanitization."""
    mock_components["github"].get_latest_run_status.return_value = {
        "databaseId": 1,
        "conclusion": "success",
        "status": "completed",
    }

    # Log contains only excluded lines
    mock_components["git"].get_log_oneline.return_value = "jules: fix\nCo-authored-by: Me"

    with pytest.raises(RuntimeError, match="Empty git log"):
        orchestrator.start_session("p", None, "j", True, 3, "m")


def test_merge_conflict(orchestrator, mock_components):
    """Test handling of merge conflict."""
    mock_components["github"].get_latest_run_status.return_value = {
        "databaseId": 1,
        "conclusion": "success",
        "status": "completed",
    }
    mock_components["git"].get_log_oneline.return_value = "feat: good"

    mock_components["deepseek"].generate_commit_info.return_value = DeepSeekCommit(
        commit_title="t", commit_body="b", branch_name="b"
    )

    mock_components["git"].merge_squash.side_effect = RuntimeError("Merge conflict")

    with pytest.raises(RuntimeError, match="Merge Conflict"):
        orchestrator.start_session("p", None, "j", True, 3, "m")


def test_wait_for_new_run_after_failure(orchestrator, mock_components):
    """Test waiting logic when run ID hasn't changed after failure."""
    statuses = [
        {"databaseId": 1, "status": "completed", "conclusion": "failure"},
        {"databaseId": 1, "status": "completed", "conclusion": "failure"},  # Still same run
        {"databaseId": 2, "status": "completed", "conclusion": "success"},  # New run
    ]
    mock_components["github"].get_latest_run_status.side_effect = statuses
    mock_components["github"].get_run_logs.return_value = "Error"

    # DeepSeek setup
    mock_components["deepseek"].generate_commit_info.return_value = DeepSeekCommit(
        commit_title="t", commit_body="b", branch_name="b"
    )
    mock_components["git"].get_log_oneline.return_value = "log"

    orchestrator.start_session("p", None, "j", True, 3, "m")

    # Should only have processed failure for run 1 ONCE
    assert mock_components["jules"].send_feedback.call_count == 1
