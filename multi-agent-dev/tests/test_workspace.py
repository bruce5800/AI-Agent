"""Workspace utility functions: name sanitization, slug derivation, hidden-path filter."""

from core.workspace import (
    _is_hidden_part,
    derive_project_slug,
    sanitize_name,
)


class TestSanitizeName:
    def test_basic_ascii(self):
        assert sanitize_name("my-project") == "my-project"

    def test_alphanumeric_preserved(self):
        assert sanitize_name("Project123_v2") == "Project123_v2"

    def test_chinese_preserved(self):
        assert sanitize_name("待办事项") == "待办事项"

    def test_chinese_and_ascii_mix(self):
        assert sanitize_name("todo待办") == "todo待办"

    def test_unsafe_chars_replaced_with_underscore(self):
        result = sanitize_name("foo!@#$bar")
        assert "!" not in result
        assert "@" not in result
        assert "#" not in result
        assert "_" in result

    def test_multiple_underscores_collapsed(self):
        assert sanitize_name("foo___bar") == "foo_bar"

    def test_trailing_underscores_stripped(self):
        assert sanitize_name("foo___") == "foo"

    def test_leading_underscores_stripped(self):
        assert sanitize_name("___foo") == "foo"

    def test_truncated_to_50(self):
        out = sanitize_name("x" * 200)
        assert len(out) == 50

    def test_empty_input_fallback(self):
        assert sanitize_name("") == "project"

    def test_only_invalid_chars_fallback(self):
        assert sanitize_name("@@@!!!") == "project"

    def test_whitespace_replaced(self):
        result = sanitize_name("hello world test")
        assert " " not in result


class TestDeriveProjectSlug:
    def test_contains_sanitized_head(self):
        slug = derive_project_slug("build a todo app")
        assert "build_a_todo_app" in slug

    def test_has_timestamp_suffix(self):
        slug = derive_project_slug("foo")
        # MMDD_HHMMSS = 11 chars after slug body
        parts = slug.split("_")
        # last two parts are MMDD and HHMMSS
        assert len(parts[-1]) == 6  # HHMMSS
        assert len(parts[-2]) == 4  # MMDD

    def test_empty_requirement(self):
        slug = derive_project_slug("")
        assert slug.startswith("project_")

    def test_long_requirement_uses_head_only(self):
        # max_chars=30 by default → only first 30 chars sanitized
        slug = derive_project_slug("x" * 100)
        # base portion (before MMDD_HHMMSS) shouldn't exceed sanitize_name's 50 cap
        # and the input was 30 chars of x's → "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        base = slug.rsplit("_", 2)[0]
        assert len(base) <= 50

    def test_chinese_requirement(self):
        slug = derive_project_slug("做一个待办事项 CLI")
        assert "做一个待办事项" in slug


class TestIsHiddenPart:
    def test_dot_dir_detected(self):
        assert _is_hidden_part((".venv", "lib", "foo.py"))
        assert _is_hidden_part(("src", ".git", "config"))

    def test_dot_file_detected(self):
        assert _is_hidden_part((".todos.json",))
        assert _is_hidden_part((".gitignore",))

    def test_normal_path_not_hidden(self):
        assert not _is_hidden_part(("src", "main.py"))
        assert not _is_hidden_part(("requirements.txt",))
        assert not _is_hidden_part(("tests", "test_foo.py"))

    def test_empty_tuple(self):
        # No parts → not hidden (defensive)
        assert not _is_hidden_part(())
