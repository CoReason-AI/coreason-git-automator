# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from pathlib import Path
from typing import Annotated, List, Optional

import typer
from rich.console import Console

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.git import GitClient
from coreason_git_automator.services.github import GitHubService
from coreason_git_automator.services.jules import JulesWrapper
from coreason_git_automator.services.workflow import WorkflowOrchestrator

app = typer.Typer(help="Coreason Git Automator - AI-driven coding assistant.")
console = Console()


@app.callback()  # type: ignore
def main() -> None:
    """
    Coreason Git Automator CLI.
    """
    pass


@app.command()  # type: ignore
def start(
    prompt: Annotated[str, typer.Argument(help="The instruction for Jules.")],
    context: Annotated[Optional[List[Path]], typer.Option(help="Local files to inject context")] = None,
    repo: Annotated[str, typer.Option(help="Target repository path (unused currently as we run in cwd)")] = ".",
    auto_fix: Annotated[bool, typer.Option(help="Enable self-healing loop")] = True,
    max_retries: Annotated[int, typer.Option(help="Maximum number of auto-fix retries")] = 3,
    base_branch: Annotated[str, typer.Option(help="Base branch to merge into")] = "main",
    jules_branch: Annotated[str, typer.Option(help="Temporary branch used by Jules")] = "jules-temp",
) -> None:
    """
    Starts an autonomous coding session.
    1. Injects context files into prompt.
    2. Starts Jules session.
    3. Enters CI/CD monitoring loop.
    4. DeepSeek squash-merges on success.
    """
    try:
        config = AutomationConfig()
        jules = JulesWrapper()
        github = GitHubService()
        deepseek = DeepSeekClient(config)
        git = GitClient()

        orchestrator = WorkflowOrchestrator(config, jules, github, deepseek, git, console)
        orchestrator.start_session(prompt, context, jules_branch, auto_fix, max_retries, base_branch)

    except Exception as e:
        # logger.exception("Automation failed") # Logged inside orchestrator
        if not isinstance(e, typer.Exit):
            raise typer.Exit(code=1) from e
        raise
