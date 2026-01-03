# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_git_automator

from git import GitCommandError, Repo

from coreason_git_automator.utils.logger import logger


class GitClient:
    """
    Client for local git operations using GitPython.
    """

    def __init__(self, repo_path: str = "."):
        try:
            self.repo = Repo(repo_path, search_parent_directories=True)
        except Exception as e:
            logger.error(f"Failed to initialize Git repository: {e}")
            raise RuntimeError(f"Failed to initialize Git repository: {e}") from e

    def get_log_oneline(self, branch: str) -> str:
        try:
            return str(self.repo.git.log("--oneline", branch))
        except GitCommandError as e:
            logger.error(f"Failed to get git log: {e}")
            raise RuntimeError(f"Failed to get git log: {e}") from e

    def checkout(self, branch: str) -> None:
        try:
            self.repo.git.checkout(branch)
        except GitCommandError as e:
            logger.error(f"Failed to checkout branch: {e}")
            raise RuntimeError(f"Failed to checkout branch: {e}") from e

    def pull(self) -> None:
        try:
            self.repo.git.pull()
        except GitCommandError as e:
            logger.error(f"Failed to pull: {e}")
            raise RuntimeError(f"Failed to pull: {e}") from e

    def create_branch(self, branch: str) -> None:
        try:
            self.repo.git.checkout("-b", branch)
        except GitCommandError as e:
            logger.error(f"Failed to create branch: {e}")
            raise RuntimeError(f"Failed to create branch: {e}") from e

    def merge_squash(self, branch: str) -> None:
        try:
            self.repo.git.merge("--squash", branch)
        except GitCommandError as e:
            logger.error(f"Failed to merge squash: {e}")
            raise RuntimeError(f"Failed to merge squash: {e}") from e

    def commit(self, title: str, body: str) -> None:
        message = f"{title}\n\n{body}"
        try:
            self.repo.git.commit("-m", message)
        except GitCommandError as e:
            logger.error(f"Failed to commit: {e}")
            raise RuntimeError(f"Failed to commit: {e}") from e

    def push(self, branch: str) -> None:
        try:
            self.repo.git.push("-u", "origin", branch)
        except GitCommandError as e:
            logger.error(f"Failed to push: {e}")
            raise RuntimeError(f"Failed to push: {e}") from e
