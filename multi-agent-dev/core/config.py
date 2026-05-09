"""Configuration for the multi-agent development system."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# DeepSeek API config (OpenAI-compatible)
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# Workspace config
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

# Agent config
MAX_TOOL_ITERATIONS = 20  # Max tool-calling loop iterations per agent call
COMMAND_TIMEOUT = 30      # Default shell command timeout (seconds)
MAX_FIX_RETRIES = 3       # Max test-fix retry loops

# Command allowlist for terminal safety.
# Only the first token of each shell segment (split by &&, ||, ;, |) is checked.
# Add more here as legitimate use cases come up.
COMMAND_ALLOWLIST: set[str] = {
    # python ecosystem
    "python", "python3", "pip", "pip3", "pytest", "uv",
    # node ecosystem
    "node", "npm", "npx", "yarn", "pnpm",
    # version control
    "git",
    # safe shell builtins / utilities (read-only or workspace-scoped)
    "ls", "cat", "echo", "pwd", "mkdir", "touch", "find", "grep",
    "head", "tail", "wc", "sort", "uniq", "true", "false",
    "cp", "mv",  # mv/cp are ok inside cwd-bound workspace
}

# Hard-deny patterns (regex). Even if executable is allowlisted, these patterns block.
COMMAND_HARD_DENY_PATTERNS = [
    r"\brm\s+-[rRf]+\s+/",      # rm -rf / (any path starting at root)
    r"\bsudo\b",
    r"\bsu\b",
    r":\(\)\s*\{",              # fork bomb
    r">\s*/dev/sd",             # raw disk write
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshutdown\b", r"\breboot\b", r"\bhalt\b", r"\bpoweroff\b",
    r"\bchmod\s+[0-7]*777\b",
]
