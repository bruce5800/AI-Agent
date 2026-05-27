"""read_file pagination + size cap behavior."""

from mcp_servers.filesystem_server import read_file


def _make_lines_file(path, n):
    """Write a file with N lines numbered L0, L1, ... LN-1."""
    path.write_text("".join(f"L{i}\n" for i in range(n)))


class TestReadFile:
    def test_small_file_full(self, tmp_path):
        (tmp_path / "a.txt").write_text("line1\nline2\n")
        assert read_file(str(tmp_path), "a.txt") == "line1\nline2\n"

    def test_missing_file(self, tmp_path):
        assert "file not found" in read_file(str(tmp_path), "ghost.txt")

    def test_default_limit_truncates_at_2000(self, tmp_path):
        _make_lines_file(tmp_path / "big.txt", 3000)
        out = read_file(str(tmp_path), "big.txt")
        assert "L0\n" in out
        assert "L1999\n" in out
        assert "L2000\n" not in out.split("…[truncated")[0]
        assert "[truncated at line 2000 of 3000" in out
        assert "offset=2000" in out

    def test_offset_continuation_window(self, tmp_path):
        _make_lines_file(tmp_path / "big.txt", 3000)
        out = read_file(str(tmp_path), "big.txt", offset=2000, limit=500)
        assert "[showing lines 2000-2499 of 3000]" in out
        assert "L2000\n" in out
        assert "L2499\n" in out
        assert "[truncated at line 2500 of 3000" in out

    def test_offset_at_eof(self, tmp_path):
        _make_lines_file(tmp_path / "a.txt", 10)
        out = read_file(str(tmp_path), "a.txt", offset=10)
        assert "EOF reached" in out

    def test_offset_past_eof(self, tmp_path):
        _make_lines_file(tmp_path / "a.txt", 10)
        out = read_file(str(tmp_path), "a.txt", offset=100)
        assert "EOF reached" in out
        assert "10 lines" in out

    def test_huge_limit_clamped(self, tmp_path):
        _make_lines_file(tmp_path / "x.txt", 50)
        # limit=999999 is clamped to 10000; file is only 50 lines so no truncation
        out = read_file(str(tmp_path), "x.txt", limit=999_999)
        assert out.count("\n") == 50
        assert "[truncated" not in out

    def test_negative_inputs_clamped(self, tmp_path):
        _make_lines_file(tmp_path / "x.txt", 5)
        out = read_file(str(tmp_path), "x.txt", offset=-100, limit=-1)
        # At least one line read (limit clamped to 1, offset clamped to 0)
        assert "L0\n" in out

    def test_byte_cap_single_giant_line(self, tmp_path):
        (tmp_path / "huge.txt").write_text("x" * 250_000)
        out = read_file(str(tmp_path), "huge.txt")
        assert len(out.encode("utf-8")) < 210_000  # 200KB + small overhead
        assert "byte cap" in out

    def test_exactly_at_limit_no_truncation_hint(self, tmp_path):
        # Exactly 2000 lines: should read all of them with NO truncation hint
        _make_lines_file(tmp_path / "exact.txt", 2000)
        out = read_file(str(tmp_path), "exact.txt")
        assert "L1999\n" in out
        assert "[truncated" not in out

    def test_blocks_traversal_via_read(self, tmp_path):
        # Defense in depth: read_file goes through _resolve_path, which
        # raises ValueError on attempts to escape the workspace.
        import pytest
        with pytest.raises(ValueError, match="Path traversal blocked"):
            read_file(str(tmp_path), "../../../etc/passwd")
