"""Pure parsers: Reviewer verdict, markdown H1 escape, OpenAI tool_call delta merge."""

from types import SimpleNamespace as NS

from agents.reviewer import parse_review
from agents.tool_agent import _merge_tool_call_delta
from ui.components import escape_h1_outside_code


class TestParseReview:
    def test_pass_marker(self):
        assert parse_review("ok\n<<<RESULT: pass>>>") == ("pass", None)

    def test_fail_marker(self):
        assert parse_review("bad\n<<<RESULT: fail>>>") == ("fail", None)

    def test_missing_marker_defaults_to_fail(self):
        """Safer than a false pass — forces another fix iteration."""
        assert parse_review("looks good") == ("fail", None)

    def test_empty_text(self):
        assert parse_review("") == ("fail", None)

    def test_escalate_to_pm(self):
        text = "ambiguous\n<<<ESCALATE: PM>>>\n<<<RESULT: fail>>>"
        assert parse_review(text) == ("fail", "PM")

    def test_last_marker_wins(self):
        """LLM occasionally emits a draft then a final marker."""
        text = "thinking <<<RESULT: pass>>>\nactually <<<RESULT: fail>>>"
        assert parse_review(text) == ("fail", None)

    def test_case_insensitive(self):
        assert parse_review("<<<result: PASS>>>")[0] == "pass"
        assert parse_review("<<<Result: Fail>>>")[0] == "fail"

    def test_escalate_without_result(self):
        # Only ESCALATE marker — should still parse the escalate target
        text = "weird <<<ESCALATE: PM>>>"
        verdict, esc = parse_review(text)
        assert esc == "PM"
        assert verdict == "fail"  # default since no RESULT marker


class TestEscapeH1OutsideCode:
    def test_single_hash_with_space_escaped(self):
        assert escape_h1_outside_code("# python comment") == "\\# python comment"

    def test_single_hash_alone_escaped(self):
        assert escape_h1_outside_code("#") == "\\#"

    def test_double_hash_preserved(self):
        assert escape_h1_outside_code("## Section") == "## Section"

    def test_triple_hash_preserved(self):
        assert escape_h1_outside_code("### Sub") == "### Sub"

    def test_six_hashes_preserved(self):
        assert escape_h1_outside_code("###### tiny") == "###### tiny"

    def test_hash_without_space_preserved(self):
        # Not a markdown heading anyway (and likely a #include or similar)
        assert escape_h1_outside_code("#nospace") == "#nospace"

    def test_inside_backtick_fence_preserved(self):
        text = "before\n```python\n# real comment\n```\n# heading outside"
        out = escape_h1_outside_code(text)
        assert "# real comment" in out          # untouched in fence
        assert "\\# heading outside" in out     # escaped outside

    def test_inside_tilde_fence_preserved(self):
        text = "~~~\n# in code\n~~~\n# outside"
        out = escape_h1_outside_code(text)
        assert "# in code" in out
        assert "\\# outside" in out

    def test_idempotent(self):
        text = "# foo\n## bar"
        once = escape_h1_outside_code(text)
        twice = escape_h1_outside_code(once)
        assert once == twice

    def test_no_hash_short_circuit(self):
        # Fast path: no '#' anywhere → returns original
        assert escape_h1_outside_code("hello\nworld") == "hello\nworld"

    def test_empty(self):
        assert escape_h1_outside_code("") == ""

    def test_multiple_h1_lines(self):
        text = "# first\nsome text\n# second"
        out = escape_h1_outside_code(text)
        assert "\\# first" in out
        assert "\\# second" in out

    def test_fence_state_tracking(self):
        # Two fenced blocks — make sure state toggles correctly
        text = "```\n# A\n```\n# B\n```\n# C\n```\n# D"
        out = escape_h1_outside_code(text)
        # A and C are inside fences (untouched), B and D are outside (escaped)
        assert "# A" in out and "\\# A" not in out
        assert "\\# B" in out
        assert "# C" in out and "\\# C" not in out
        assert "\\# D" in out


def _tc_delta(index, id=None, name=None, args=None):
    """Build an OpenAI-style streaming tool_call delta."""
    return NS(
        index=index, id=id, type="function" if id else None,
        function=NS(name=name, arguments=args),
    )


class TestMergeToolCallDelta:
    def test_complete_single_chunk(self):
        slots = []
        _merge_tool_call_delta(slots, _tc_delta(0, id="c1", name="foo", args='{"x":1}'))
        assert slots == [{
            "id": "c1", "type": "function",
            "function": {"name": "foo", "arguments": '{"x":1}'},
        }]

    def test_fragmented_arguments_accumulate(self):
        slots = []
        _merge_tool_call_delta(slots, _tc_delta(0, id="c1", name="f", args='{"pa'))
        _merge_tool_call_delta(slots, _tc_delta(0, args='th":"foo"}'))
        assert slots[0]["function"]["arguments"] == '{"path":"foo"}'

    def test_two_parallel_calls(self):
        slots = []
        _merge_tool_call_delta(slots, _tc_delta(0, id="c1", name="read"))
        _merge_tool_call_delta(slots, _tc_delta(1, id="c2", name="write"))
        assert [s["function"]["name"] for s in slots] == ["read", "write"]
        assert slots[0]["id"] == "c1"
        assert slots[1]["id"] == "c2"

    def test_interleaved_argument_streams(self):
        slots = []
        _merge_tool_call_delta(slots, _tc_delta(0, id="c1", name="r", args='{"a'))
        _merge_tool_call_delta(slots, _tc_delta(1, id="c2", name="w", args='{"b'))
        _merge_tool_call_delta(slots, _tc_delta(0, args='":1}'))
        _merge_tool_call_delta(slots, _tc_delta(1, args='":2}'))
        assert slots[0]["function"]["arguments"] == '{"a":1}'
        assert slots[1]["function"]["arguments"] == '{"b":2}'

    def test_sparse_index_grows_list(self):
        # Only index=2 arrives — list grows to 3 slots with empty placeholders
        slots = []
        _merge_tool_call_delta(slots, _tc_delta(2, id="c3", name="x"))
        assert len(slots) == 3
        assert slots[0] == {"id": "", "type": "function",
                            "function": {"name": "", "arguments": ""}}
        assert slots[2]["id"] == "c3"

    def test_name_concatenates_if_fragmented(self):
        # Rare but possible: name comes in two pieces
        slots = []
        _merge_tool_call_delta(slots, _tc_delta(0, id="c1", name="read_"))
        _merge_tool_call_delta(slots, _tc_delta(0, name="file"))
        assert slots[0]["function"]["name"] == "read_file"
