import json

import pytest

from vidfactory import scripting
from vidfactory.models import VidFactoryError
from vidfactory.styles import STYLES


def test_extract_json_from_fenced_reply():
    reply = 'Claro:\n```json\n{"title": "T", "scenes": [{"text": "a"}]}\n```'
    assert scripting.extract_json(reply)["title"] == "T"


def test_extract_json_rejects_garbage():
    with pytest.raises(VidFactoryError):
        scripting.extract_json("no es json")


def test_template_writer_respects_scene_count(cfg):
    cfg["script"]["scenes"] = 3
    script = scripting.write_script("gatos", STYLES.get("kinetic"), cfg)
    assert len(script.scenes) == 3 and "gatos" in script.scenes[0].text


def test_countdown_gets_numbered_labels(cfg):
    cfg["script"]["scenes"] = 3
    script = scripting.write_script("gatos", STYLES.get("countdown"), cfg)
    assert [s.label for s in script.scenes] == ["3", "2", "1"]


def test_prompt_mentions_style_and_topic(cfg):
    prompt = scripting.build_prompt("volcanes", STYLES.get("countdown"), cfg)
    assert "volcanes" in prompt and "countdown" in prompt and "label" in prompt


def test_script_file_with_plain_string_scenes(cfg, tmp_path):
    f = tmp_path / "g.json"
    f.write_text(json.dumps({"title": "Hola", "scenes": ["uno", "dos"]}), encoding="utf-8")
    script = scripting.load_script_file(f, STYLES.get("kinetic"), cfg)
    assert [s.text for s in script.scenes] == ["uno", "dos"]


def test_empty_script_rejected(cfg, tmp_path):
    f = tmp_path / "g.json"
    f.write_text('{"title": "x", "scenes": []}', encoding="utf-8")
    with pytest.raises(VidFactoryError):
        scripting.load_script_file(f, STYLES.get("kinetic"), cfg)
