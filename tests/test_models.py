import pytest
from pydantic import ValidationError

from coreason_git_automator.models import AutomationConfig, DeepSeekCommit


def test_deepseek_commit_valid():
    """Test creating a valid DeepSeekCommit."""
    commit = DeepSeekCommit(
        commit_title="feat(core): add new feature",
        commit_body="- Added new feature\n- Fixed bug",
        branch_name="feat/new-feature",
    )
    assert commit.commit_title == "feat(core): add new feature"
    assert commit.commit_body == "- Added new feature\n- Fixed bug"
    assert commit.branch_name == "feat/new-feature"


def test_deepseek_commit_invalid_branch_name():
    """Test that DeepSeekCommit rejects invalid branch names."""
    with pytest.raises(ValidationError):
        DeepSeekCommit(
            commit_title="fix: bad branch",
            commit_body="...",
            branch_name="Fix/Bad Branch!",  # Invalid chars: spaces, uppercase, exclamation
        )


def test_deepseek_commit_missing_fields():
    """Test validation when required fields are missing."""
    with pytest.raises(ValidationError):
        DeepSeekCommit(commit_title="oops")


def test_automation_config_valid_env(monkeypatch):
    """Test loading AutomationConfig from environment variables."""
    monkeypatch.setenv("JULES_API_KEY", "jules123")
    monkeypatch.setenv("GITHUB_TOKEN", "gh123")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds123")

    config = AutomationConfig()
    assert config.jules_api_key.get_secret_value() == "jules123"
    assert config.github_token.get_secret_value() == "gh123"
    assert config.deepseek_api_key.get_secret_value() == "ds123"


def test_automation_config_missing_env(monkeypatch):
    """Test that AutomationConfig fails when env vars are missing."""
    # Ensure env vars are cleared
    monkeypatch.delenv("JULES_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        AutomationConfig()
