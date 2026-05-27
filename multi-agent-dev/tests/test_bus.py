"""MessageBus mechanics: drain semantics, priority order, audit log preservation."""

from core.bus import MessageBus, TeamMessage


def _msg(sender="X", recipient="Y", msg_type="task", content="", **meta):
    return TeamMessage(
        sender=sender, recipient=recipient,
        msg_type=msg_type, content=content, metadata=meta,
    )


class TestMessageBus:
    def test_send_drain_roundtrip(self):
        bus = MessageBus()
        bus.send(_msg("A", "B", content="hi"))
        bus.send(_msg("A", "B", content="ho"))
        msgs = bus.drain("B")
        assert [m.content for m in msgs] == ["hi", "ho"]

    def test_drain_clears_inbox(self):
        bus = MessageBus()
        bus.send(_msg("A", "B"))
        bus.drain("B")
        assert bus.drain("B") == []

    def test_drain_unknown_recipient_empty(self):
        bus = MessageBus()
        assert bus.drain("nobody") == []

    def test_drain_fifo_order(self):
        bus = MessageBus()
        for i in range(5):
            bus.send(_msg("A", "B", content=f"m{i}"))
        msgs = bus.drain("B")
        assert [m.content for m in msgs] == [f"m{i}" for i in range(5)]

    def test_audit_log_keeps_everything(self):
        bus = MessageBus()
        bus.send(_msg("A", "B"))
        bus.send(_msg("B", "C"))
        bus.drain("B")  # drain does NOT remove from audit
        assert len(bus.audit) == 2
        assert bus.audit[0].sender == "A"
        assert bus.audit[1].recipient == "C"

    def test_has_pending(self):
        bus = MessageBus()
        assert not bus.has_pending()
        bus.send(_msg("A", "B"))
        assert bus.has_pending()
        bus.drain("B")
        assert not bus.has_pending()

    def test_peek_does_not_drain(self):
        bus = MessageBus()
        bus.send(_msg("A", "B", content="x"))
        peeked = bus.peek("B")
        assert len(peeked) == 1
        # Still drainable
        assert len(bus.drain("B")) == 1

    def test_next_pending_respects_priority(self):
        bus = MessageBus()
        bus.send(_msg("X", "Reviewer"))
        bus.send(_msg("X", "PM"))
        bus.send(_msg("X", "User"))
        # priority dictates User comes first even though it was sent last
        assert bus.next_pending(["User", "PM", "Reviewer"]) == "User"

    def test_next_pending_skips_empty_recipients(self):
        bus = MessageBus()
        bus.send(_msg("X", "Programmer"))
        # User/PM/Architect all empty → falls through to Programmer
        assert bus.next_pending(["User", "PM", "Architect", "Programmer"]) == "Programmer"

    def test_next_pending_fallback_when_priority_misses(self):
        bus = MessageBus()
        bus.send(_msg("X", "WeirdRole"))
        # Priority doesn't include "WeirdRole" but next_pending finds it anyway
        result = bus.next_pending(["User", "PM"])
        assert result == "WeirdRole"

    def test_next_pending_returns_none_when_empty(self):
        bus = MessageBus()
        assert bus.next_pending(["User", "PM"]) is None

    def test_drain_preserves_metadata(self):
        bus = MessageBus()
        bus.send(_msg("A", "B", phase="design", next_agent="Programmer"))
        m = bus.drain("B")[0]
        assert m.metadata == {"phase": "design", "next_agent": "Programmer"}


class TestTeamMessage:
    def test_unique_ids(self):
        m1 = _msg()
        m2 = _msg()
        assert m1.id != m2.id

    def test_default_metadata_empty_dict(self):
        m = _msg()
        assert m.metadata == {}

    def test_independent_metadata_dicts(self):
        # Default factory must not share the dict across instances
        m1 = _msg()
        m2 = _msg()
        m1.metadata["x"] = 1
        assert "x" not in m2.metadata
