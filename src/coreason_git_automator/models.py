from pydantic import BaseModel, Field


class DeepSeekCommit(BaseModel):
    """
    Model representing the structured commit output from DeepSeek.
    """

    commit_title: str = Field(..., description="Conventional commit title", min_length=1)
    commit_body: str = Field(..., description="Detailed bullet points", min_length=1)
    branch_name: str = Field(..., pattern=r"^[a-z0-9/-]+$")
