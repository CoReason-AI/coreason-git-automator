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
from typing import Any, Dict, List, Optional

from rich.console import Console
from tenacity import RetryError, Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from coreason_git_automator.config import AutomationConfig
from coreason_git_automator.services.ai import DeepSeekClient
from coreason_git_automator.services.git import GitClient
from coreason_git_automator.services.github import GitHubService
from coreason_git_automator.services.jules import JulesWrapper
from coreason_git_automator.utils.logger import logger


class RunFailedError(Exception):
    """Raised when a CI run fails, triggering a feedback loop."""

    pass


class PollingWaitError(Exception):
    """Raised when CI is still running or queued."""

    pass


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
        Monitors the CI/CD pipeline using tenacity for robust retries.
        """
        last_processed_run_id: Optional[str] = None

        def attempt_fix() -> None:
            nonlocal last_processed_run_id
            # 1. Wait for a conclusive run result
            run = self._wait_for_run_completion(branch, last_processed_run_id)
            current_run_id = str(run.get("databaseId"))
            conclusion = run.get("conclusion")

            if conclusion == "success":
                self.console.print("[bold green]CI passed![/bold green]")
                return  # Success

            if conclusion == "failure":
                # Update state BEFORE raising
                last_processed_run_id = current_run_id

                self.console.print(f"[bold red]CI failed (Run {current_run_id}). Fetching logs...[/bold red]")
                logs = self.github.get_run_logs(current_run_id)
                last_50_lines = "\n".join(logs.splitlines()[-50:])

                self.console.print("[bold red]Sending feedback to Jules...[/bold red]")
                self.jules.send_feedback(last_50_lines)

                # Trigger retry
                raise RunFailedError(f"Run {current_run_id} failed")

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(max_retries + 1),
                reraise=False,  # We want to catch RetryError
                retry=retry_if_exception_type(RunFailedError),
            ):
                with attempt:
                    attempt_fix()
        except RetryError:
            self.console.print(f"[bold red]Max retries ({max_retries}) exceeded. Aborting.[/bold red]")
            raise RuntimeError(f"Max retries ({max_retries}) exceeded.") from None

    def _wait_for_run_completion(self, branch: str, last_seen_id: Optional[str]) -> Dict[str, Any]:
        """
        Polls until a valid, completed run is found.
        """
        polling_retry = Retrying(
            wait=wait_fixed(10),
            retry=retry_if_exception_type(PollingWaitError),
            reraise=True,
        )

        def poll_step() -> Dict[str, Any]:
            with self.console.status("[bold yellow]Monitoring CI/CD...[/bold yellow]") as status:
                run_status = self.github.get_latest_run_status(branch)

                if not run_status:
                    status.update("[bold yellow]No run found yet...[/bold yellow]")
                    raise PollingWaitError("No run found")

                run_id = str(run_status.get("databaseId"))
                state = run_status.get("status")

                if last_seen_id and run_id == last_seen_id:
                    status.update("[bold yellow]Waiting for new run after failure...[/bold yellow]")
                    raise PollingWaitError("Waiting for new run")

                if state in ["queued", "in_progress"]:
                    status.update("[bold yellow]Waiting for CI...[/bold yellow]")
                    raise PollingWaitError("CI in progress")

                return run_status

        for attempt in polling_retry:
            with attempt:
                return poll_step()

        raise RuntimeError("Unreachable")  # pragma: no cover

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
