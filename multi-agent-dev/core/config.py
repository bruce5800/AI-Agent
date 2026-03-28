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

# Command denylist for terminal safety
COMMAND_DENYLIST = [
    "rm -rf /", "rm -rf ~", "sudo", "mkfs", "dd if=",
    "shutdown", "reboot", ":(){ :|:& };:",
]
