"""Run with: pytest  (no network needed; Google News and xAI are replaced by canned data)."""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.industry_tracker.news import (  # noqa: E402
    build_grok_payload, build_news_query, classify_type, enrich_item, fetch_google_news, find_company,
    find_regions, google_news_url, grok_briefing, parse_google_news, parse_grok_response, skills_in_news, time_ago,
)

RSS = b"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
<item><title>Google lays off 199 engineers in the US as Cloud and cybersecurity teams shrink - Example News</title>
<link>https://example.com/a</link><pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate><source url="https://example.com">Example News</source></item>
<item><title>Infosys hiring 5,000 freshers in India for AI and Python roles - Mint</title>
<link>https://example.com/b</link><pubDate>Fri, 30 Oct 2026 08:30:00 GMT</pubDate><source url="https://mint.com">Mint</source></item>
<item><title>Infosys hiring 5,000 freshers in India for AI and Python roles - Mint</title>
<link>https://example.com/b2</link><pubDate>Fri, 30 Oct 2026 08:31:00 GMT</pubDate><source url="https://mint.com">Mint</source></item>
<item><title>Bad link item</title><link>javascript:alert(1)</link></item>
</channel></rss>"""


def test_rss_parsing_dedupes_sorts_and_rejects_bad_links():
    items = parse_google_news(RSS)
    assert [i["link"] for i in items] == ["https://example.com/b", "https://example.com/a"]   # newest first
    assert items[1]["title"].endswith("shrink") and items[1]["source"] == "Example News"      # source suffix removed


def test_classification_regions_company_skills():
    a, b = [enrich_item(i) for i in parse_google_news(RSS)][::-1]
    assert a["type"] == "Layoffs" and a["company"] == "Google" and "USA" in a["regions"]
    assert {"Cloud Computing", "Cybersecurity"} <= set(a["skills"])
    assert b["type"] == "Hiring" and b["company"] == "Infosys" and "India" in b["regions"]
    assert "Python" in b["skills"] and b["ai"] is True
    assert skills_in_news([a, b])["Python"] == 1


def test_us_and_canada_detection():
    assert "USA" in find_regions("Meta cuts jobs at U.S. offices")
    assert "Canada" in find_regions("Shopify expands Toronto hub")
    assert find_company("Why Microsoft and Google are cutting jobs") == "Microsoft"
    assert classify_type("Quarterly earnings beat estimates") == "Other"


def test_urls_and_queries():
    url = google_news_url("tech layoffs", 7, "CA")
    assert "when%3A7d" in url and "ceid=CA%3Aen" in url
    assert build_news_query("tech layoffs", ["Google", "Tata Consultancy"]) == '(Google OR "Tata Consultancy") (tech layoffs)'


def test_fetch_uses_injected_opener_and_hides_network_errors():
    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return RSS
    assert len(fetch_google_news("x", opener=lambda req, timeout: Resp())) == 2
    def boom(req, timeout): raise OSError("secret internals")
    with pytest.raises(RuntimeError, match="Couldn't reach Google News"):
        fetch_google_news("x", opener=boom)


def test_time_ago():
    now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    assert time_ago(now - timedelta(minutes=5), now) == "5 min ago"
    assert time_ago(now - timedelta(hours=3), now) == "3 h ago"
    assert time_ago(now - timedelta(days=2), now) == "2 d ago"


GROK = {"output": [
    {"type": "reasoning"},
    {"type": "web_search_call"},
    {"type": "message", "content": [{"type": "output_text", "text": "Briefing text",
        "annotations": [{"type": "url_citation", "url": "https://a.example", "title": "A"},
                        {"type": "url_citation", "url": "https://a.example", "title": "A again"}]}]}]}


def test_grok_response_parsing():
    r = parse_grok_response(GROK)
    assert r["text"] == "Briefing text" and r["searched"] is True and r["sources"] == [{"title": "A", "url": "https://a.example"}]
    assert parse_grok_response({"output": [{"type": "message", "content": [{"type": "output_text", "text": "x"}]}]})["searched"] is False


def test_grok_request_shape_and_key_safety():
    seen = {}
    class R:
        status_code = 200
        def json(self): return GROK
    def post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return R()
    out = grok_briefing("xai-SECRET", "latest layoffs", post=post)
    assert seen["url"] == "https://api.x.ai/v1/responses" and seen["headers"]["Authorization"] == "Bearer xai-SECRET"
    assert seen["json"]["tools"] == [{"type": "web_search"}] and seen["json"] == build_grok_payload("latest layoffs")
    assert out["text"] == "Briefing text"

    class Bad:
        status_code = 401
    for code, exc in [(401, PermissionError), (404, RuntimeError), (429, RuntimeError), (500, RuntimeError)]:
        Bad.status_code = code
        with pytest.raises(exc) as e:
            grok_briefing("xai-SECRET", "x", post=lambda *a, **k: Bad())
        assert "xai-SECRET" not in str(e.value)

    def net_error(*a, **k): raise ConnectionError("xai-SECRET leaked?")
    with pytest.raises(RuntimeError) as e:
        grok_briefing("xai-SECRET", "x", post=net_error)
    assert "xai-SECRET" not in str(e.value)
    with pytest.raises(ValueError):
        grok_briefing("  ", "x", post=post)
