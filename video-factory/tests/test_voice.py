import sys

import pytest

from vidfactory import voice
from vidfactory.models import VidFactoryError
from vidfactory.render import ffmpeg_exe


def test_distribute_words_covers_whole_duration():
    words = voice.distribute_words("hola mundo cruel", 3.0)
    assert len(words) == 3
    assert words[0].start == 0 and words[-1].end == pytest.approx(3.0)
    assert all(a.end == pytest.approx(b.start) for a, b in zip(words, words[1:]))


def test_silent_voice_duration_scales_with_text(tmp_path):
    cfg = None
    v = voice.SilentVoice(cfg)
    short, long = tmp_path / "s.wav", tmp_path / "l.wav"
    v.synth("hola", short)
    v.synth(" ".join(["palabra"] * 25), long)
    assert voice.wav_duration(long) > voice.wav_duration(short)


def test_command_backend_runs_user_program_and_uses_cache(cfg, tmp_path):
    script = tmp_path / "fake_tts.py"
    script.write_text(
        "import sys, wave\n"
        "text = open(sys.argv[1], encoding='utf-8').read()\n"
        "w = wave.open(sys.argv[2], 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)\n"
        "w.writeframes(b'\\x00\\x00' * 16000 * max(1, len(text.split())))\n"
        "open(sys.argv[2] + '.calls', 'a').write('x')\n",
        encoding="utf-8",
    )
    cfg["voice"]["backend"] = "command"
    cfg["voice"]["command"]["args"] = [sys.executable, str(script), "{text_file}", "{out}"]
    from vidfactory.models import Script

    s = Script.from_dict({"title": "t", "scenes": ["uno dos", "tres"]})
    run = tmp_path / "run"
    run.mkdir()
    audio = voice.synthesize(s, cfg, run, ffmpeg_exe(), log=lambda *_: None)
    assert s.scenes[0].duration == pytest.approx(2 + 0.25, abs=0.05)
    assert voice.wav_duration(audio) == pytest.approx(sum(sc.duration for sc in s.scenes), abs=0.05)
    # segunda corrida: todo sale de la caché, no se vuelve a invocar el TTS
    before = sorted(p.name for p in (tmp_path / "cache" / "voice").iterdir())
    voice.synthesize(s, cfg, run, ffmpeg_exe(), log=lambda *_: None)
    assert before == sorted(p.name for p in (tmp_path / "cache" / "voice").iterdir())


def test_command_backend_requires_out_placeholder(cfg):
    cfg["voice"]["backend"] = "command"
    cfg["voice"]["command"]["args"] = ["echo", "hola"]
    assert "{out}" in voice.CommandVoice(cfg).check()


def test_command_failure_is_reported(cfg, tmp_path):
    cfg["voice"]["command"]["args"] = [sys.executable, "-c", "import sys; sys.exit('boom')", "{out}"]
    with pytest.raises(VidFactoryError, match="boom"):
        voice.CommandVoice(cfg).synth("hola", tmp_path / "o.wav")
