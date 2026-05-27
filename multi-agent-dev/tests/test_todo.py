"""todo_write validation, replace semantics, load_todos roundtrip."""

import json

from mcp_servers.todo_server import todo_write, load_todos


class TestTodoWrite:
    def test_basic_write(self, tmp_path):
        out = todo_write(str(tmp_path), [
            {"content": "step 1", "status": "pending"},
            {"content": "step 2", "status": "in_progress", "activeForm": "Doing step 2"},
        ])
        assert "Saved 2 todos" in out
        todos = load_todos(str(tmp_path))
        assert len(todos) == 2
        assert todos[0] == {"content": "step 1", "status": "pending"}
        assert todos[1]["activeForm"] == "Doing step 2"

    def test_persisted_to_dot_todos_json(self, tmp_path):
        todo_write(str(tmp_path), [{"content": "x", "status": "pending"}])
        path = tmp_path / ".todos.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data[0]["content"] == "x"

    def test_replace_semantics_not_merge(self, tmp_path):
        todo_write(str(tmp_path), [{"content": "first", "status": "pending"}])
        todo_write(str(tmp_path), [{"content": "second", "status": "completed"}])
        todos = load_todos(str(tmp_path))
        assert len(todos) == 1
        assert todos[0]["content"] == "second"

    def test_invalid_status(self, tmp_path):
        out = todo_write(str(tmp_path), [{"content": "x", "status": "DONE"}])
        assert "Error" in out
        assert "DONE" in out

    def test_missing_content(self, tmp_path):
        out = todo_write(str(tmp_path), [{"status": "pending"}])
        assert "Error" in out
        assert "missing 'content'" in out

    def test_blank_content(self, tmp_path):
        out = todo_write(str(tmp_path), [{"content": "   ", "status": "pending"}])
        # Whitespace-only is treated as empty
        assert "Error" in out

    def test_not_a_list(self, tmp_path):
        out = todo_write(str(tmp_path), "not a list")
        assert "Error" in out
        assert "list" in out

    def test_item_not_a_dict(self, tmp_path):
        out = todo_write(str(tmp_path), ["a string"])
        assert "Error" in out
        assert "must be a dict" in out

    def test_empty_active_form_dropped(self, tmp_path):
        todo_write(str(tmp_path), [
            {"content": "x", "status": "pending", "activeForm": ""},
        ])
        todos = load_todos(str(tmp_path))
        assert "activeForm" not in todos[0]

    def test_counts_summary(self, tmp_path):
        out = todo_write(str(tmp_path), [
            {"content": "a", "status": "completed"},
            {"content": "b", "status": "completed"},
            {"content": "c", "status": "in_progress"},
            {"content": "d", "status": "pending"},
        ])
        assert "2 ✅" in out
        assert "1 🔄" in out
        assert "1 ⏳" in out


class TestLoadTodos:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_todos(str(tmp_path)) == []

    def test_corrupt_json_returns_empty(self, tmp_path):
        (tmp_path / ".todos.json").write_text("not { valid json")
        assert load_todos(str(tmp_path)) == []

    def test_non_list_json_returns_empty(self, tmp_path):
        (tmp_path / ".todos.json").write_text('{"oops": "not a list"}')
        assert load_todos(str(tmp_path)) == []

    def test_roundtrip(self, tmp_path):
        todos = [
            {"content": "a", "status": "pending"},
            {"content": "b", "status": "in_progress", "activeForm": "doing b"},
        ]
        todo_write(str(tmp_path), todos)
        loaded = load_todos(str(tmp_path))
        assert loaded == todos
