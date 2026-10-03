import pytest

from vidfactory.config import DEFAULTS, Config, deep_merge


@pytest.fixture
def cfg(tmp_path):
    data = deep_merge(DEFAULTS, {"render": {"encoder": "libx264"}})
    return Config(data, tmp_path)
