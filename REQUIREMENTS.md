# Software Requirements for Coreason Git Automator

## 1. FUNCTIONAL REQUIREMENT DOCUMENT (FRD)

### 1.1 Core Logic: The JulesWrapper
The tool acts as a Python wrapper around the `@google/jules` NPM package.

*   **Discovery:** Assume `jules` is in the system PATH. Verify via `jules --version`.
*   **Session Start:** Use subprocess to call `jules remote new`.
*   **Context Injection (Critical):**
    *   The user may provide local files via a `--context` flag (e.g., `--context src/main.py`).
    *   You must read these files and prepend their content to the prompt sent to Jules.
    *   **Format:**
        ```text
        [CONTEXT: src/main.py]
        <file_content>

        [INSTRUCTION]
        <user_prompt>
        ```
*   **Feedback Loop:** Use `jules remote` commands to feed CI/CD error logs back to the active session.

### 1.2 The Self-Healing Loop
**Monitor:** Poll the GitHub Action run status for the current branch using `gh api` (JSON).

**Logic:**
*   **Status: queued/in_progress** → Show `rich.spinner` "Waiting for CI...".
*   **Status: failure** → Fetch logs via GitHub API, extract the last 50 lines, and send to Jules: "Fix the code based on these errors."
*   **Status: success** → Proceed to Phase 3.

### 1.3 Merge & Polish Strategy (DeepSeek Intelligence)
*   **Input Data:** Fetch the raw `git log --oneline` from the temporary Jules branch. Sanitize it by removing lines containing "jules" or "Co-authored-by".
*   **The Intelligence Step:** You must implement a `DeepSeekClient` that sends the raw log to the DeepSeek API with the following specific instructions:

    **System Prompt:**
    > "You are a Senior Release Engineer. Analyze the provided git commit log. Your goal is to consolidate the work into a single 'Conventional Commit' message and suggest a clean git branch name. Output purely valid JSON with no markdown formatting."

    **User Prompt:** `<raw_git_log>`

    **Required JSON Structure:**
    The API must return (and your code must validate) this exact schema:
    ```json
    {
      "commit_title": "<type>(<scope>): <concise summary>",
      "commit_body": "<bullet points of technical changes>",
      "branch_name": "<type>/<short-kebab-case-description>"
    }
    ```

**Execution:**
1.  Checkout develop (or main) and pull latest.
2.  Create the new branch using `branch_name` from the JSON.
3.  Squash merge the temporary Jules branch: `git merge --squash <jules_temp_branch>`.
4.  Commit using the `commit_title` and `commit_body` from the JSON.
5.  Push and open a PR.

## 2. TECHNICAL ARCHITECTURE (King Stack)

### 2.1 Data Models (`src/coreason_git_automator/models.py`)
Use Pydantic for all internal data structures.

```python
class DeepSeekCommit(BaseModel):
    commit_title: str = Field(..., description="Conventional commit title")
    commit_body: str = Field(..., description="Detailed bullet points")
    branch_name: str = Field(..., pattern=r"^[a-z0-9/-]+$")

class AutomationConfig(BaseSettings):
    jules_api_key: SecretStr = Field(alias="JULES_API_KEY")
    github_token: SecretStr = Field(alias="GITHUB_TOKEN")
    deepseek_api_key: SecretStr = Field(alias="DEEPSEEK_API_KEY")
```

### 2.2 CLI Interface (`src/coreason_git_automator/cli.py`)
Use `typer.Typer` with `rich` for all user interactions.

```python
@app.command()
def start(
    prompt: str,
    context: List[Path] = typer.Option(None, help="Local files to inject context"),
    repo: str = typer.Option(".", help="Target repository"),
    auto_fix: bool = typer.Option(True, help="Enable self-healing loop")
):
    """
    Starts an autonomous coding session.
    1. Injects context files into prompt.
    2. Starts Jules session.
    3. Enters CI/CD monitoring loop.
    4. DeepSeek squash-merges on success.
    """
    ...
```

### 2.3 GitHub Service (`src/coreason_git_automator/services/github.py`)
*   **Strictly API-First:** Do not parse `gh` CLI text output. Use `gh api` with the `--json` flag.

## 3. IMMEDIATE ACTION PLAN
Perform the following steps strictly in order:

1.  **Dependencies:** Verify or install the "King" stack: `poetry add "typer[all]>=0.9.0" "pydantic>=2.0" "rich>=13.0" "tenacity" "httpx"`.
2.  **Config Module:** Implement `src/<slug>/config.py`.
3.  **DeepSeek Service:** Implement `src/<slug>/services/ai.py` with the JSON prompting logic defined in FRD 1.3.
4.  **Jules Service:** Implement `src/<slug>/services/jules.py` with the context injection logic.
5.  **GitHub Service:** Implement `src/<slug>/services/github.py`.
6.  **CLI Entrypoint:** Wire the services together in `src/<slug>/main.py`.
