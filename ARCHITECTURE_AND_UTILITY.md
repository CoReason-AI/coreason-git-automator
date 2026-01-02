# The Architecture and Utility of coreason_git_automator

### 1. The Philosophy (The Why)

In the modern software development landscape, there exists a friction-heavy gap between *intent* and *implementation*. Developers often find themselves in a "flow state" (or "vibe"), only to be interrupted by the administrative toil of git operations, CI/CD polling, and iterative bug fixing. `coreason_git_automator` was born from the desire to preserve this flow state—a concept we call "Vibe Coding."

This package is not merely a CLI tool; it is an autonomous agentic wrapper designed to sit between the developer's creative mind and the rigid requirements of the repository. The standard library and existing git wrappers offer *mechanism* but lack *agency*. They require the developer to drive every step. `coreason_git_automator` flips this model: the developer provides the high-level intent, and the software assumes responsibility for the "Code-Fix-Ship" lifecycle. It creates a self-healing feedback loop where the tool writes code, verifies it against CI, auto-corrects based on failure logs, and finally packages the result into a clean, human-readable Pull Request. It allows the engineer to focus on the *what* while the automation handles the *how*.

### 2. Under the Hood (The Dependencies & logic)

The architecture of `coreason_git_automator` is built upon the "Category King" stack, chosen specifically to support resilience, clarity, and strict correctness in an autonomous environment.

*   **`typer` & `click`**: These provide the structural skeleton of the application. `typer` is used to create a strongly-typed, intuitive Command Line Interface that minimizes runtime errors and maximizes developer ergonomics.
*   **`rich`**: Serving as the "UX layer," `rich` transforms the terminal into a highly readable dashboard. In an autonomous loop where the machine is doing the work, clear visual feedback is critical to build trust with the human observer.
*   **`tenacity`**: This library acts as the application's resilience layer. Network calls to GitHub or AI endpoints are inherently flaky; `tenacity` ensures that the automator can gracefully recover from transient failures without crashing the user's session.
*   **`pydantic` & `pydantic-settings`**: These enforce strict data validation and configuration management. By treating configuration as a typed contract, the system ensures that it never operates on invalid state, which is crucial when an agent is making commits on your behalf.
*   **`httpx`**: The asynchronous networking engine that powers the high-performance communication with the DeepSeek and GitHub APIs.
*   **`loguru`**: Provides centralized, structured logging, ensuring that every decision made by the autonomous agent is auditable and transparent.

Internally, the logic operates as a state machine. Upon receiving an instruction, it spins up a `JulesWrapper` session to generate code. It then enters a monitoring loop, polling GitHub Actions via `httpx`. If a failure is detected, the logs are harvested, filtered, and fed back into the AI to produce a fix. Once the CI passes (Green Build), the tool uses a secondary AI model (DeepSeek) to analyze the chaotic "work-in-progress" git history and synthesize a clean, semantic commit message, effectively "squashing" the noise into a signal before creating a Pull Request.

### 3. In Practice (The How)

The power of `coreason_git_automator` lies in its ability to take a natural language prompt and convert it into a merged pull request. Here is how it looks in practice.

**The "Happy Path" Automation**

The primary entry point is the `start` command. You provide the intent, and the tool handles the entire lifecycle, including the self-healing CI loop.

```python
from coreason_git_automator.cli import app

# In a script, one might invoke the automation loop directly.
# This single command initiates the AI session, monitors CI,
# auto-fixes bugs, and prepares the final PR.
app(
    [
        "start",
        "Refactor the user authentication module to use JWT tokens.",
        "--base-branch", "main",
        "--auto-fix"  # Enables the self-healing CI/CD loop
    ]
)
```

**Injecting Context for Complex Tasks**

For more nuanced tasks, you can inject specific file contexts to ground the AI's generation. This ensures the "Brain" (DeepSeek/Jules) has the exact local knowledge required.

```python
from pathlib import Path
from coreason_git_automator.services.jules import JulesWrapper

# Programmatic access to the wrapper allows for custom workflows
jules = JulesWrapper()

# The tool accepts paths to give the AI "eyes" on the relevant code
context_files = [
    Path("src/auth/models.py"),
    Path("src/auth/utils.py")
]

# The session runs, and the automator will subsequently
# handle the git operations based on the result.
jules.run_session(
    prompt="Add a refresh token mechanism to the existing models.",
    context_files=context_files
)
```
