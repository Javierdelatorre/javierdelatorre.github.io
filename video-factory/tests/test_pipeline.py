import re
import subprocess

import pytest
from PIL import Image

from vidfactory.models import Scene, Script
from vidfactory.pipeline import make_video, slugify
from vidfactory.render import ffmpeg_exe, video_size
from vidfactory.styles import STYLES


def probe(path):
    err = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s), err


def test_slugify_removes_accents_and_symbols():
    assert slugify("¿Qué pasó con el dólar?!") == "que-paso-con-el-dolar"


def test_video_size():
    assert video_size("vertical", False) == (1080, 1920)
    assert video_size("horizontal", True) == (960, 540)


@pytest.mark.parametrize("name", STYLES.names())
def test_every_style_draws_correct_frame_size(name, tmp_path):
    style = STYLES.get(name)((270, 480), 30, {}, tmp_path)
    script = Script.from_dict({"title": "T", "scenes": [{"text": "hola mundo", "label": "1"}]})
    script.scenes[0].duration = 2.0
    from vidfactory.voice import distribute_words

    script.scenes[0].words = distribute_words("hola mundo", 1.5)
    style.prepare(script)
    for t in (0.0, 0.5, 1.9):
        assert style.frame(0, script.scenes[0], t).size == (270, 480)


@pytest.mark.parametrize("name", STYLES.names())
def test_make_video_end_to_end(name, cfg):
    cfg["script"]["scenes"] = 2
    result = make_video(cfg, "tema de prueba", name, draft=True, log=lambda *_: None)
    assert result.video.is_file() and result.script_path.is_file()
    duration, info = probe(result.video)
    assert duration == pytest.approx(result.seconds, abs=0.2)
    assert "540x960" in info and "Audio: aac" in info


def test_slideshow_uses_images_from_assets(cfg, tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    Image.new("RGB", (800, 600), (200, 30, 30)).save(assets / "rojo.png")
    style = STYLES.get("slideshow")((270, 480), 30, {}, assets)
    script = Script(title="t", scenes=[Scene("hola", duration=2.0)])
    style.prepare(script)
    r, g, b = style.frame(0, script.scenes[0], 0.0).getpixel((135, 20))
    assert r > 150 and g < 90  # se ve la imagen roja, no el degradado
