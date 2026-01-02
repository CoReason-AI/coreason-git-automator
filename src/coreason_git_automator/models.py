# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from pydantic import BaseModel, Field


class DeepSeekCommit(BaseModel):
    """
    Model for the commit information returned by DeepSeek.
    """
    commit_title: str = Field(..., description="Conventional commit title")
    commit_body: str = Field(..., description="Detailed bullet points")
    branch_name: str = Field(..., pattern=r"^[a-z0-9/-]+$")
