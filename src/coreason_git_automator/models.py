from pydantic import BaseModel, Field


class DeepSeekCommit(BaseModel):
    """
    Model representing the structured commit output from DeepSeek.
    """

    commit_title: str = Field(..., description="Conventional commit title")
    commit_body: str = Field(..., description="Detailed bullet points")
    branch_name: str = Field(..., pattern=r"^[a-z0-9/-]+$")
