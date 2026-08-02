import pytest

from app.admin.fs_browse import InvalidPath, list_directory


def _mk_tree(root):
    root.mkdir()
    (root / "a.mp3").write_bytes(b"x" * 100)
    (root / "b.mp3").write_bytes(b"x" * 200)
    (root / "sub").mkdir()
    (root / "sub" / "c.mp3").write_bytes(b"x" * 300)
    (root / "sub" / "nested").mkdir()
    (root / "sub" / "nested" / "d.mp3").write_bytes(b"x" * 400)
    (root / ".hidden.mp3").write_bytes(b"x" * 10)
    (root / "not-mp3.txt").write_text("nope")


def test_lists_root(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    r = list_directory(root, "")
    assert [f.name for f in r.folders] == ["sub"]
    assert [f.name for f in r.files] == ["a.mp3", "b.mp3"]
    assert r.rel_path == ""
    assert r.breadcrumb == [type(r.breadcrumb[0])(name="Library", rel_path="")]


def test_lists_subfolder(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    r = list_directory(root, "sub")
    assert [f.name for f in r.folders] == ["nested"]
    assert [f.name for f in r.files] == ["c.mp3"]
    assert r.rel_path == "sub"


def test_lists_nested_folder(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    r = list_directory(root, "sub/nested")
    assert [f.name for f in r.folders] == []
    assert [f.name for f in r.files] == ["d.mp3"]
    assert r.rel_path == "sub/nested"


def test_breadcrumb_multi_level(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    r = list_directory(root, "sub/nested")
    assert [(c.name, c.rel_path) for c in r.breadcrumb] == [
        ("Library", ""),
        ("sub", "sub"),
        ("nested", "sub/nested"),
    ]


def test_rejects_dotdot(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    with pytest.raises(InvalidPath):
        list_directory(root, "..")
    with pytest.raises(InvalidPath):
        list_directory(root, "sub/../../etc")
    with pytest.raises(InvalidPath):
        list_directory(root, "../etc")


def test_rejects_absolute_path(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    with pytest.raises(InvalidPath):
        list_directory(root, "/etc")


def test_skips_dotfiles(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    r = list_directory(root, "")
    assert ".hidden.mp3" not in [f.name for f in r.files]


def test_only_mp3_files(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    r = list_directory(root, "")
    assert "not-mp3.txt" not in [f.name for f in r.files]


def test_missing_folder_raises(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    with pytest.raises(InvalidPath):
        list_directory(root, "does-not-exist")


def test_file_size_populated(tmp_path):
    root = tmp_path / "music"
    _mk_tree(root)
    r = list_directory(root, "")
    files_by_name = {f.name: f.size_bytes for f in r.files}
    assert files_by_name["a.mp3"] == 100
    assert files_by_name["b.mp3"] == 200
