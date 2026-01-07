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


def test_deepseek_commit_empty_fields():
    """Test validation prevents empty commit title or body."""
    with pytest.raises(ValidationError) as exc:
        DeepSeekCommit(commit_title="", commit_body="", branch_name="valid-branch")
    errors = exc.value.errors()
    assert any(e["loc"] == ("commit_title",) and "String should have at least 1 character" in e["msg"] for e in errors)
    assert any(e["loc"] == ("commit_body",) and "String should have at least 1 character" in e["msg"] for e in errors)
