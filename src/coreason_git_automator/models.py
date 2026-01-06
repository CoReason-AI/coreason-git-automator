from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings


class DeepSeekCommit(BaseModel):
    """
    Model representing the structured commit output from DeepSeek.
    """

    commit_title: str = Field(..., description="Conventional commit title")
    commit_body: str = Field(..., description="Detailed bullet points")
    branch_name: str = Field(..., pattern=r"^[a-z0-9/-]+$")


class AutomationConfig(BaseSettings):
    """
    Configuration for the automation tool, loaded from environment variables.
    """

    jules_api_key: SecretStr = Field(alias="JULES_API_KEY")
    github_token: SecretStr = Field(alias="GITHUB_TOKEN")
    deepseek_api_key: SecretStr = Field(alias="DEEPSEEK_API_KEY")
