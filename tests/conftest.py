import os
import tempfile
from pathlib import Path

_tmp_data = Path(tempfile.mkdtemp(prefix="bitvelox-test-"))
_tmp_music = Path(tempfile.mkdtemp(prefix="bitvelox-music-"))
os.environ.setdefault("DATA_DIR", str(_tmp_data))
os.environ.setdefault("MUSIC_DIR", str(_tmp_music))
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
