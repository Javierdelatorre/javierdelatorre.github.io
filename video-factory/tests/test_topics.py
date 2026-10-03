import pytest

from vidfactory import topics
from vidfactory.models import VidFactoryError

RSS = """<?xml version="1.0"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel>
<item><title>Tema pequeño</title><ht:approx_traffic>200+</ht:approx_traffic></item>
<item><title>Tema gigante</title><ht:approx_traffic>2M+</ht:approx_traffic></item>
<item><title>Tema medio</title><ht:approx_traffic>50K+</ht:approx_traffic></item>
</channel></rss>"""


def test_parse_traffic():
    assert topics.parse_traffic("200+") == 200
    assert topics.parse_traffic("50K+") == 50_000
    assert topics.parse_traffic("2M+") == 2_000_000
    assert topics.parse_traffic(None) == 0


def test_parse_trends_rss_orders_by_traffic(cfg, monkeypatch):
    monkeypatch.setitem(topics.PROVIDERS._items, "trends", lambda c: topics.parse_trends_rss(RSS))
    result = topics.suggest(cfg, limit=2, provider="trends")
    assert [t.title for t in result] == ["Tema gigante", "Tema medio"]


def test_file_provider_ignores_comments(cfg, tmp_path):
    (tmp_path / "topics.txt").write_text("# nota\nprimero\n\nsegundo\n", encoding="utf-8")
    assert [t.title for t in topics.suggest(cfg, provider="file")] == ["primero", "segundo"]


def test_unknown_provider(cfg):
    with pytest.raises(VidFactoryError, match="Disponibles"):
        topics.suggest(cfg, provider="nada")
