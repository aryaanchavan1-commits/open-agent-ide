import pytest
from pathlib import Path

from app.tools.files import (
    WorkspaceError,
    create_directory,
    delete_file,
    edit_file,
    list_directory,
    read_file,
    resolve_path,
    search_files,
    search_text,
    write_file,
)


@pytest.fixture
def ws(tmp_path):
    return tmp_path / "workspace"


@pytest.fixture
def project_dir(tmp_path):
    d = tmp_path / "project-001"
    (d / "source").mkdir(parents=True)
    return d


def test_resolve_path_rejects_traversal(ws):
    with pytest.raises(WorkspaceError):
        resolve_path(ws, "../escape.txt")
    with pytest.raises(WorkspaceError):
        resolve_path(ws, "..\\escape.txt")


def test_write_read_file(ws):
    result = write_file(ws, "src/app.py", "print('hi')")
    assert result["ok"]
    data = read_file(ws, "src/app.py")
    assert data["content"] == "print('hi')"


def test_write_file_no_overwrite(ws):
    write_file(ws, "a.txt", "one")
    result = write_file(ws, "a.txt", "two", overwrite=False)
    assert not result["ok"]
    assert read_file(ws, "a.txt")["content"] == "one"


def test_edit_file_exact(ws):
    write_file(ws, "a.py", "x = 1\ny = 2\n")
    result = edit_file(ws, "a.py", "x = 1", "x = 10")
    assert result["ok"]
    assert read_file(ws, "a.py")["content"] == "x = 10\ny = 2\n"


def test_edit_file_fuzzy(ws):
    write_file(ws, "a.py", "def foo():\n    return 1\n\ndef bar():\n    return 2\n")
    result = edit_file(ws, "a.py", "def bar():\n    return 2", "def bar():\n    return 3")
    assert result["ok"]
    assert "return 3" in read_file(ws, "a.py")["content"]


def test_edit_file_missing_snippet(ws):
    write_file(ws, "a.py", "hello")
    result = edit_file(ws, "a.py", "nope", "yes")
    assert not result["ok"]


def test_delete_file(ws):
    write_file(ws, "a.txt", "x")
    assert delete_file(ws, "a.txt")["ok"]
    assert not read_file(ws, "a.txt")["ok"]


def test_delete_protected_dir(ws):
    ws.mkdir(parents=True)
    (ws / ".git").mkdir()
    result = delete_file(ws, ".git")
    assert not result["ok"]


def test_list_directory(ws):
    create_directory(ws, "src/utils")
    write_file(ws, "src/utils/h.py", "")
    entries = list_directory(ws, "src")["entries"]
    assert any(e["name"] == "utils" and e["type"] == "directory" for e in entries)


def test_search_files(ws):
    write_file(ws, "one.py", "")
    write_file(ws, "two.js", "")
    matches = search_files(ws, "*.py")["matches"]
    assert matches == ["one.py"]


def test_search_text(ws):
    write_file(ws, "a.py", "def handle_user(): pass\n")
    matches = search_text(ws, "handle_user")["matches"]
    assert len(matches) == 1
    assert matches[0]["file"] == "a.py"
