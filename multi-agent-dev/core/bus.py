"""In-memory message bus for inter-agent communication.

Inspired by docs/s09 — every agent has a logical inbox; agents communicate by
sending typed messages rather than via a hard-coded pipeline. Unlike s09 this
implementation is single-threaded and lives entirely in process memory: the
Streamlit UI drives one iteration at a time via the engine's generator, which
is the natural shape for synchronous streaming. The mailbox semantics
(per-recipient ordered queue, drain-on-read, audit log) are the same.

Message types
-------------
- ``task``             - "please do this", initial assignment from User/peer
- ``approval_request`` - "draft ready, please approve" (recipient="User")
- ``fix_request``      - "this is broken, please fix" (Reviewer → Programmer)
- ``escalation``       - cross-phase escalation (e.g. Reviewer → PM when the
                         requirements themselves are contradictory)
- ``done``             - pipeline finished (recipient="User")

Routing
-------
There is **no** centralised state machine. Each agent decides where its output
goes in its own ``handle()`` method — including dynamic options like
escalating to a previous role. The engine just drives the bus: drain the next
non-empty inbox, run that agent, forward whatever it produces.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TeamMessage:
    sender: str
    recipient: str
    msg_type: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    in_reply_to: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


class MessageBus:
    """Per-recipient ordered queue with full audit log."""

    def __init__(self) -> None:
        self._inboxes: dict[str, list[TeamMessage]] = defaultdict(list)
        self.audit: list[TeamMessage] = []

    def send(self, msg: TeamMessage) -> None:
        self._inboxes[msg.recipient].append(msg)
        self.audit.append(msg)

    def drain(self, recipient: str) -> list[TeamMessage]:
        msgs = self._inboxes[recipient]
        self._inboxes[recipient] = []
        return msgs

    def peek(self, recipient: str) -> list[TeamMessage]:
        return list(self._inboxes[recipient])

    def has_pending(self) -> bool:
        return any(msgs for msgs in self._inboxes.values())

    def next_pending(self, priority: list[str]) -> str | None:
        """Return the next recipient with pending messages.

        Tries `priority` first (so e.g. "User" approval requests are surfaced
        before peer-to-peer chatter); falls back to any non-empty inbox.
        """
        for name in priority:
            if self._inboxes.get(name):
                return name
        for name, msgs in self._inboxes.items():
            if msgs:
                return name
        return None
