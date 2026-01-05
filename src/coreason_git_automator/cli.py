# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

import time
from pathlib import Path
from typing import Annotated, List, Optional

import typer
from rich.console import Console

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.git import GitClient
from coreason_git_automator.services.github import GitHubService
from coreason_git_automator.services.jules import JulesWrapper
from coreason_git_automator.utils.logger import logger

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

        # 1. Verify Dependencies
        console.print(f"[bold green]Found Jules version: {jules.verify_version()}[/bold green]")
        console.print(f"[bold green]Found GitHub CLI version: {github.verify_installed()}[/bold green]")

        # 2. Start Session
        console.print("[bold blue]Starting Jules session...[/bold blue]")
        jules.run_session(prompt, context)

        # 3. Monitor Loop
        if auto_fix:
            last_processed_run_id = None
            consecutive_failures = 0
            with console.status("[bold yellow]Monitoring CI/CD...[/bold yellow]") as status:
                while True:
                    if consecutive_failures >= max_retries:
                        console.print(f"[bold red]Max retries ({max_retries}) exceeded. Aborting.[/bold red]")
                        raise typer.Exit(code=1)

                    run_status = github.get_latest_run_status(jules_branch)

                    if not run_status:
                        # Maybe wait for run to start?
                        time.sleep(5)
                        continue

                    run_id = str(run_status.get("databaseId"))
                    conclusion = run_status.get("conclusion")
                    state = run_status.get("status")

                    if state in ["queued", "in_progress"]:
                        status.update("[bold yellow]Waiting for CI...[/bold yellow]")
                        time.sleep(10)
                        continue

                    if conclusion == "success":
                        console.print("[bold green]CI passed![/bold green]")
                        break

                    if conclusion == "failure":
                        if run_id == last_processed_run_id:
                            # Already processed this failure, wait for new run
                            status.update("[bold yellow]Waiting for new run after failure...[/bold yellow]")
                            time.sleep(10)
                            continue

                        console.print(f"[bold red]CI failed (Run {run_id}). Fetching logs...[/bold red]")
                        logs = github.get_run_logs(run_id)

                        # Extract last 50 lines
                        last_50_lines = "\n".join(logs.splitlines()[-50:])

                        console.print("[bold red]Sending feedback to Jules...[/bold red]")
                        jules.send_feedback(last_50_lines)
                        last_processed_run_id = run_id
                        consecutive_failures += 1

                        # Wait for Jules to push fixes
                        time.sleep(10)
                        continue

        # 4. Merge & Polish
        console.print("[bold magenta]Preparing to merge...[/bold magenta]")

        # Fetch git log
        raw_log = git.get_log_oneline(jules_branch)

        # Sanitize (simple filter)
        sanitized_log = "\n".join(
            line for line in raw_log.splitlines() if "jules" not in line.lower() and "Co-authored-by" not in line
        )

        if not sanitized_log.strip():
            console.print("[bold red]Empty git log after sanitization. Aborting.[/bold red]")
            raise typer.Exit(code=1)

        # Intelligence Step
        console.print("[bold cyan]Consulting DeepSeek...[/bold cyan]")
        commit_info = deepseek.generate_commit_info(sanitized_log)

        console.print(f"Generated Plan:\nTitle: {commit_info.commit_title}\nBranch: {commit_info.branch_name}")

        # Execution
        git.checkout(base_branch)
        git.pull()
        git.create_branch(commit_info.branch_name)
        try:
            git.merge_squash(jules_branch)
        except RuntimeError as e:
            console.print("[bold red]Git operation failed (Merge Conflict).[/bold red]")
            raise typer.Exit(code=1) from e

        git.commit(commit_info.commit_title, commit_info.commit_body)
        git.push(commit_info.branch_name)

        pr_url = github.create_pr(
            commit_info.commit_title, commit_info.commit_body, commit_info.branch_name, base_branch
        )

        console.print(f"[bold green]PR Created: {pr_url}[/bold green]")

    except Exception as e:
        logger.exception("Automation failed")
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()  # pragma: no cover
