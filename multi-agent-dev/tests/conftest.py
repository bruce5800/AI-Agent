"""pytest config — make ``multi-agent-dev/`` importable, supply test env defaults.

Some modules (e.g. ``core.config``) read env vars at import time. We set
harmless defaults here so test runs don't need a real ``.env``.
"""

import os
import sys

# tests/ lives inside multi-agent-dev/. Put the project root on sys.path so
# `from core.bus import ...` works regardless of where pytest was invoked.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key-for-tests")
