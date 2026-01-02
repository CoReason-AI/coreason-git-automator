# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import pytest
from pydantic import ValidationError

from coreason_git_automator.models import DeepSeekCommit


def test_deepseek_commit_valid():
    """Test valid DeepSeekCommit model creation."""
    commit = DeepSeekCommit(
        commit_title="feat(core): add new feature",
        commit_body="- Added new feature\n- Updated tests",
        branch_name="feat/new-feature-1",
    )
    assert commit.commit_title == "feat(core): add new feature"
    assert commit.branch_name == "feat/new-feature-1"


def test_deepseek_commit_invalid_branch_name():
    """Test DeepSeekCommit model with invalid branch name."""
    with pytest.raises(ValidationError):
        DeepSeekCommit(
            commit_title="feat(core): add new feature", commit_body="...", branch_name="Invalid Branch Name!"
        )


def test_deepseek_commit_missing_fields():
    """Test DeepSeekCommit model with missing fields."""
    with pytest.raises(ValidationError):
        DeepSeekCommit(commit_title="feat(core): add new feature")
