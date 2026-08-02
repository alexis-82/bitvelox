import logging

from app.logging_setup import setup_logging


def test_writes_to_stdout_and_file(tmp_path, capsys):
    setup_logging(tmp_path / "logs")
    log = logging.getLogger("test_stdout_file")

    log.warning("hello-world-marker")

    for h in logging.getLogger().handlers:
        h.flush()

    log_file = tmp_path / "logs" / "server.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello-world-marker" in content

    captured = capsys.readouterr()
    assert "hello-world-marker" in captured.out


def test_rotation_creates_backup(tmp_path):
    from app.logging_setup import setup_logging as _setup
    from app import logging_setup as ls

    ls.MAX_BYTES = 500  # shrink for test
    _setup(tmp_path / "logs")
    log = logging.getLogger("test_rotation")

    for i in range(200):
        log.info("padding message %d %s", i, "x" * 20)

    for h in logging.getLogger().handlers:
        h.flush()

    logs_dir = tmp_path / "logs"
    files = sorted(p.name for p in logs_dir.iterdir())
    assert "server.log" in files
    assert any(f.startswith("server.log.") for f in files), files

    ls.MAX_BYTES = 10 * 1024 * 1024  # restore
