"""Git worktree session — isolate speculative fix attempts.

Concept (docs/s12)
------------------
Each Reviewer-triggered fix iteration is risky: the patch might make things
worse than they were. If we apply it directly to the main workspace we have
nothing to roll back to. A git worktree gives us a separate working tree
sharing the same .git directory, so we can:

  main workspace  (HEAD: feat: initial impl)
        │
        └── worktree fix/attempt-1  (HEAD: feat: initial impl)
                ↓ Programmer writes fix
                ↓ commit "fix attempt #1"
                ↓ Reviewer tests
                ├─ pass → `git merge --squash fix/attempt-1` into main
                └─ fail/escalation → `git worktree remove` (discard)

The agents themselves don't need to know about worktrees — the engine swaps
``agent.workspace`` before dispatching, so all filesystem tools and run_command
calls land in the isolated dir. After merge/discard, main is unchanged on
failure, and atomically updated on success.

Why not let agents own worktree lifecycle?
- Lifecycle is cross-cutting (spans multiple Reviewer/Programmer dispatches)
- subprocess + filesystem state needs deterministic management
- An LLM is the wrong tool for "rm -rf this dir if test failed"
"""

from __future__ import annotations

import os
import subprocess


GIT_USER_EMAIL = "agent@multi-agent-dev.local"
GIT_USER_NAME = "Multi-Agent Dev"


def _run_git(cwd: str, *args: str, timeout: int = 30) -> tuple[int, str]:
    """Run a git subcommand. Returns (returncode, combined stdout+stderr)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (result.stdout + result.stderr).strip()
        return result.returncode, out
    except FileNotFoundError:
        return 127, "Error: git not found on PATH"
    except subprocess.TimeoutExpired:
        return 124, f"Error: git timed out after {timeout}s"
    except Exception as e:
        return 1, f"Error: {e!s}"


class WorktreeSession:
    """One active fix-attempt worktree at a time, branched off main.

    States: idle → active (after start) → idle (after merge_to_main or discard).
    A new ``start()`` after an exit creates ``fix/attempt-N+1``.
    """

    def __init__(self, main_workspace: str):
        self.main = main_workspace
        self.path: str | None = None
        self.branch: str | None = None
        self._counter = 0

    # ---------- main repo bootstrapping ----------

    def is_main_repo(self) -> bool:
        return os.path.isdir(os.path.join(self.main, ".git"))

    def init_main(self) -> str:
        """`git init` + configure identity. Idempotent."""
        if not self.is_main_repo():
            rc, out = _run_git(self.main, "init", "-b", "main")
            _run_git(self.main, "config", "user.email", GIT_USER_EMAIL)
            _run_git(self.main, "config", "user.name", GIT_USER_NAME)
            return out or "(initialized)"
        return "(already a repo)"

    def commit_main(self, message: str) -> str:
        """Stage everything and commit on main. Returns short summary."""
        _run_git(self.main, "add", "-A")
        rc, out = _run_git(self.main, "commit", "-m", message)
        if rc != 0 and ("nothing to commit" in out or "no changes added" in out):
            return "(no changes to commit)"
        # Trim noisy hook output etc. to one-liner
        first_line = out.splitlines()[0] if out else "(commit)"
        return first_line

    def main_has_commits(self) -> bool:
        rc, _ = _run_git(self.main, "rev-parse", "--verify", "HEAD")
        return rc == 0

    # ---------- worktree lifecycle ----------

    def is_active(self) -> bool:
        return self.path is not None

    def start(self) -> str:
        """Create a new worktree branched off main's HEAD."""
        if self.is_active():
            return f"(worktree already active at {self.path})"
        if not self.main_has_commits():
            return "Error: main has no commits yet — cannot branch"

        self._counter += 1
        n = self._counter
        branch = f"fix/attempt-{n}"
        worktree_path = f"{self.main}__fix_{n}"

        rc, out = _run_git(
            self.main, "worktree", "add", "-b", branch, worktree_path, "HEAD"
        )
        if rc != 0:
            return f"Error: {out}"

        self.path = worktree_path
        self.branch = branch
        # Worktrees share .git, so the user.email/user.name set on main repo
        # already applies; no need to re-set.
        return f"worktree created: {worktree_path} (branch {branch})"

    def commit_attempt(self, message: str) -> str:
        """Stage + commit inside the active worktree."""
        if not self.is_active():
            return "(no active worktree)"
        _run_git(self.path, "add", "-A")
        rc, out = _run_git(self.path, "commit", "-m", message)
        if rc != 0 and ("nothing to commit" in out or "no changes added" in out):
            return "(no changes in worktree)"
        first_line = out.splitlines()[0] if out else "(commit)"
        return first_line

    def merge_to_main(self, message: str = "fix: merge speculative fix") -> str:
        """Squash-merge the fix branch into main, then remove the worktree."""
        if not self.is_active():
            return "(no active worktree)"
        branch = self.branch

        # Squash merge keeps main's history linear: one commit per accepted fix
        # session regardless of how many attempts happened inside.
        rc, out = _run_git(self.main, "merge", "--squash", branch)
        if rc != 0:
            _run_git(self.main, "merge", "--abort")
            cleanup = self.discard()
            return f"Error during squash-merge: {out}\n{cleanup}"

        _run_git(self.main, "add", "-A")
        rc, commit_out = _run_git(self.main, "commit", "-m", message)
        commit_line = commit_out.splitlines()[0] if commit_out else "(commit)"

        cleanup = self.discard()
        return f"merged: {commit_line} | {cleanup}"

    def discard(self) -> str:
        """Remove the worktree (and its branch) without merging."""
        if not self.is_active():
            return "(no active worktree)"
        path, branch = self.path, self.branch
        # Clear state first so re-entrancy is safe even if the rm fails.
        self.path = None
        self.branch = None
        rc1, out1 = _run_git(self.main, "worktree", "remove", "--force", path)
        rc2, out2 = _run_git(self.main, "branch", "-D", branch)
        return f"worktree removed ({path}); branch deleted ({branch})"
