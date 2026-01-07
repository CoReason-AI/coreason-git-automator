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
from typing import List, Optional

from rich.console import Console

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.git import GitClient
from coreason_git_automator.services.github import GitHubService
from coreason_git_automator.services.jules import JulesWrapper
from coreason_git_automator.utils.logger import logger


class WorkflowOrchestrator:
    """
    Orchestrates the 'Code-Fix-Ship' autonomous coding session.
    """

    def __init__(
        self,
        config: AutomationConfig,
        jules: JulesWrapper,
        github: GitHubService,
        deepseek: DeepSeekClient,
        git: GitClient,
        console: Console,
    ) -> None:
        self.config = config
        self.jules = jules
        self.github = github
        self.deepseek = deepseek
        self.git = git
        self.console = console

    def start_session(
        self,
        prompt: str,
        context: Optional[List[Path]],
        jules_branch: str,
        auto_fix: bool,
        max_retries: int,
        base_branch: str,
    ) -> None:
        """
        Executes the full workflow:
        1. Verify Environment
        2. Start Jules Session
        3. Monitor CI/CD (Self-Healing)
        4. Merge & Polish (Commit & PR)
        """
        try:
            # 1. Verify Dependencies
            self.console.print(f"[bold green]Found Jules version: {self.jules.verify_installed()}[/bold green]")
            self.console.print(f"[bold green]Found GitHub CLI version: {self.github.verify_installed()}[/bold green]")

            # 2. Start Session
            self.console.print("[bold blue]Starting Jules session...[/bold blue]")
            self.git.ensure_branch(jules_branch)
            self.jules.run_session(prompt, context)

            # 3. Monitor Loop
            if auto_fix:
                self._monitor_ci_loop(jules_branch, max_retries)

            # 4. Merge & Polish
            self._perform_merge_and_push(jules_branch, base_branch)

        except Exception as e:
            logger.exception("Automation failed")
            self.console.print(f"[bold red]Error: {e}[/bold red]")
            raise

    def _monitor_ci_loop(self, branch: str, max_retries: int) -> None:
        """
        Monitors the CI/CD pipeline and feeds back errors to Jules.
        """
        last_processed_run_id = None
        consecutive_failures = 0

        with self.console.status("[bold yellow]Monitoring CI/CD...[/bold yellow]") as status:
            while True:
                if consecutive_failures >= max_retries:
                    self.console.print(f"[bold red]Max retries ({max_retries}) exceeded. Aborting.[/bold red]")
                    raise RuntimeError(f"Max retries ({max_retries}) exceeded.")

                run_status = self.github.get_latest_run_status(branch)

                if not run_status:
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
                    self.console.print("[bold green]CI passed![/bold green]")
                    break

                if conclusion == "failure":
                    if run_id == last_processed_run_id:
                        status.update("[bold yellow]Waiting for new run after failure...[/bold yellow]")
                        time.sleep(10)
                        continue

                    self.console.print(f"[bold red]CI failed (Run {run_id}). Fetching logs...[/bold red]")
                    logs = self.github.get_run_logs(run_id)
                    last_50_lines = "\n".join(logs.splitlines()[-50:])

                    self.console.print("[bold red]Sending feedback to Jules...[/bold red]")
                    self.jules.send_feedback(last_50_lines)
                    last_processed_run_id = run_id
                    consecutive_failures += 1
                    time.sleep(10)
                    continue

    def _perform_merge_and_push(self, jules_branch: str, base_branch: str) -> None:
        """
        Squash merges the work and pushes it with a conventional commit message.
        """
        self.console.print("[bold magenta]Preparing to merge...[/bold magenta]")

        raw_log = self.git.get_log_oneline(jules_branch)
        sanitized_log = "\n".join(
            line for line in raw_log.splitlines() if "jules" not in line.lower() and "Co-authored-by" not in line
        )

        if not sanitized_log.strip():
            self.console.print("[bold red]Empty git log after sanitization. Aborting.[/bold red]")
            raise RuntimeError("Empty git log after sanitization.")

        self.console.print("[bold cyan]Consulting DeepSeek...[/bold cyan]")
        commit_info = self.deepseek.generate_commit_info(sanitized_log)

        self.console.print(f"Generated Plan:\nTitle: {commit_info.commit_title}\nBranch: {commit_info.branch_name}")

        self.git.checkout(base_branch)
        self.git.pull()
        self.git.create_branch(commit_info.branch_name)
        try:
            self.git.merge_squash(jules_branch)
        except RuntimeError as e:
            self.console.print("[bold red]Git operation failed (Merge Conflict).[/bold red]")
            raise RuntimeError("Merge Conflict") from e

        self.git.commit(commit_info.commit_title, commit_info.commit_body)
        self.git.push(commit_info.branch_name)

        pr_url = self.github.create_pr(
            commit_info.commit_title, commit_info.commit_body, commit_info.branch_name, base_branch
        )

        self.console.print(f"[bold green]PR Created: {pr_url}[/bold green]")
