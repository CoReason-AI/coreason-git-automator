from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from coreason_git_automator.cli import app
from coreason_git_automator.main import main

runner = CliRunner()


@pytest.fixture
def mock_orchestrator():
    with patch("coreason_git_automator.cli.WorkflowOrchestrator") as mock:
        yield mock


@pytest.fixture
def mock_config():
    with patch("coreason_git_automator.cli.AutomationConfig") as mock:
        yield mock


@pytest.fixture
def mock_dependencies():
    with (
        patch("coreason_git_automator.cli.JulesWrapper") as m1,
        patch("coreason_git_automator.cli.GitHubService") as m2,
        patch("coreason_git_automator.cli.DeepSeekClient") as m3,
        patch("coreason_git_automator.cli.GitClient") as m4,
    ):
        yield {"jules": m1, "github": m2, "deepseek": m3, "git": m4}


def test_start_command(mock_orchestrator, mock_config, mock_dependencies):
    """Test start command happy path."""
    result = runner.invoke(app, ["start", "Do something"])
    assert result.exit_code == 0

    # Verify orchestrator called
    mock_orchestrator.return_value.start_session.assert_called_once()
    args = mock_orchestrator.return_value.start_session.call_args
    assert args[0][0] == "Do something"


def test_start_command_with_options(mock_orchestrator, mock_config, mock_dependencies):
    """Test start command with options."""
    result = runner.invoke(
        app,
        [
            "start",
            "Task",
            "--no-auto-fix",
            "--max-retries",
            "5",
            "--base-branch",
            "develop",
            "--jules-branch",
            "feature-x",
        ],
    )
    assert result.exit_code == 0

    args = mock_orchestrator.return_value.start_session.call_args
    # start_session(prompt, context, jules_branch, auto_fix, max_retries, base_branch)
    # Check keyword args or positional depending on call
    # Typer uses positional for argument, but function signature is:
    # prompt, context, jules_branch, auto_fix, max_retries, base_branch

    # Check auto_fix is False
    assert args[0][3] is False
    # max_retries 5
    assert args[0][4] == 5


def test_start_command_exception(mock_orchestrator, mock_config, mock_dependencies):
    """Test handling of unexpected exceptions."""
    mock_orchestrator.return_value.start_session.side_effect = Exception("Boom")

    # Typer catches exceptions but we want to ensure we handle it gracefully or exit 1
    # The CLI code catches Exception and raises Typer.Exit(1)

    result = runner.invoke(app, ["start", "Task"])
    assert result.exit_code == 1


def test_start_command_typer_exit_exception(mock_orchestrator, mock_config, mock_dependencies):
    """Test handling of Typer.Exit exception (pass through)."""
    mock_orchestrator.return_value.start_session.side_effect = typer.Exit(code=2)

    result = runner.invoke(app, ["start", "Task"])
    assert result.exit_code == 2


def test_main_function():
    """Test main entry point."""
    with patch("coreason_git_automator.main.app") as mock_app:
        main()
        mock_app.assert_called_once()
