import pytest
from pydantic import ValidationError

from coreason_git_automator.models import DeepSeekCommit


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
