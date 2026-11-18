"""Live industry news for the Curriculum Alignment Analyzer (no Streamlit imports).

* Headlines come from the public Google News RSS feed (no API key needed).
* An optional Grok briefing uses the xAI Responses API with the built-in
  ``web_search`` tool. The API key is only ever sent in the Authorization
  header and never logged, stored or put in an error message.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from modules.curriculum_analyzer import extract_skills_from_text

NEWS_PRESETS = {
    "Tech layoffs": "tech layoffs OR job cuts OR layoffs",
    "Tech hiring": "tech hiring OR software engineer jobs OR hiring developers",
    "AI jobs & skills": "AI engineer hiring OR AI skills demand OR machine learning jobs",
    "Fresher / campus hiring": "fresher hiring IT companies OR campus placements",
}
NEWS_EDITIONS = {"India": "IN", "United States": "US", "Canada": "CA", "United Kingdom": "GB"}
NEWS_COMPANIES = [
    "Google", "Microsoft", "Amazon", "Meta", "Apple", "Netflix", "Intel", "IBM", "Oracle", "Salesforce",
    "Nvidia", "Tesla", "TCS", "Infosys", "Wipro", "HCLTech", "Accenture", "Cognizant", "Capgemini",
    "eBay", "Qualcomm", "Workday", "Barclays", "OpenAI", "Anthropic", "xAI",
]
_EDITION_PARAMS = {"IN": ("en-IN", "IN", "IN:en"), "US": ("en-US", "US", "US:en"),
                   "CA": ("en-CA", "CA", "CA:en"), "GB": ("en-GB", "GB", "GB:en")}

_LAYOFF = re.compile(
    r"\b(lay(?:s|ing)?[- ]?offs?|laid off|job cuts?|cuts? (?:\d[\d,]* )?(?:jobs|roles|positions|workforce|staff)"
    r"|fires?|fired|redundanc\w+|downsiz\w+|buyouts?|axes|slash\w*)\b", re.I)
_HIRING = re.compile(
    r"\b(hiring|hires?|recruit\w*|job openings?|job postings?|talent demand|adds? \d[\d,]* jobs"
    r"|expands? (?:its )?(?:team|workforce)|opens? (?:a )?(?:new )?(?:office|hub|centre|center))\b", re.I)
_REGIONS = {
    "USA": re.compile(r"\b(usa|united states|american|california|bay area|seattle|new york|texas|washington state)\b", re.I),
    "Canada": re.compile(r"\b(canada|canadian|toronto|vancouver|waterloo|montreal|ottawa)\b", re.I),
    "India": re.compile(r"\b(india|indian|bengaluru|bangalore|hyderabad|pune|chennai|gurugram|gurgaon|noida|mumbai)\b", re.I),
    "UK": re.compile(r"\b(uk|u\.k\.|britain|british|london)\b", re.I),
    "Europe": re.compile(r"\b(europe|european|germany|german|france|french|sweden|swedish|ireland|dublin|netherlands)\b", re.I),
    "Asia-Pacific": re.compile(r"\b(taiwan|china|chinese|japan|singapore|australia|korea)\b", re.I),
}
_US_CASE_SENSITIVE = re.compile(r"\bU\.?S\.?(?![\w])")
_AI = re.compile(r"\bAI\b|(?i:artificial intelligence|machine learning|generative ai|llms?)")


def google_news_url(query: str, days: int = 7, edition: str = "IN") -> str:
    hl, gl, ceid = _EDITION_PARAMS.get(edition, _EDITION_PARAMS["IN"])
    params = {"q": f"{query} when:{int(days)}d", "hl": hl, "gl": gl, "ceid": ceid}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


def build_news_query(preset_query: str, companies: list[str]) -> str:
    if not companies:
        return preset_query
    names = " OR ".join(f'"{c}"' if " " in c else c for c in companies)
    return f"({names}) ({preset_query})"


def parse_google_news(xml_bytes: bytes) -> list[dict]:
    """Parse a Google News RSS document into a list of headline dicts (newest first)."""
    root = ET.fromstring(xml_bytes)
    out, seen = [], set()
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        src_el = item.find("source")
        source = (src_el.text or "").strip() if src_el is not None and src_el.text else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].rstrip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        key = re.sub(r"\W+", " ", title.lower())[:70]
        if key in seen:
            continue
        seen.add(key)
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published = None
        out.append({"title": title, "source": source or "Google News", "link": link, "published": published})
    floor = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(out, key=lambda x: x["published"] or floor, reverse=True)


def fetch_google_news(query: str, days: int = 7, edition: str = "IN", limit: int = 40,
                      timeout: float = 10.0, opener=urllib.request.urlopen) -> list[dict]:
    req = urllib.request.Request(google_news_url(query, days, edition),
                                 headers={"User-Agent": "Mozilla/5.0 (CurriculumIQ news reader)"})
    try:
        with opener(req, timeout=timeout) as resp:
            data = resp.read()
    except Exception as exc:  # network down, blocked, timeout
        raise RuntimeError(f"Couldn't reach Google News ({type(exc).__name__}). Check your internet connection.") from None
    try:
        return parse_google_news(data)[:limit]
    except ET.ParseError:
        raise RuntimeError("Google News returned something that isn't a news feed. Try again in a minute.") from None


def classify_type(title: str) -> str:
    if _LAYOFF.search(title):
        return "Layoffs"
    if _HIRING.search(title):
        return "Hiring"
    return "Other"


def find_regions(title: str) -> list[str]:
    found = [name for name, pat in _REGIONS.items() if pat.search(title)]
    if "USA" not in found and _US_CASE_SENSITIVE.search(title):
        found.insert(0, "USA")
    return found


def find_company(title: str) -> str:
    best = None
    for name in NEWS_COMPANIES:
        m = re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", title)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name)
    return best[1] if best else ""


def enrich_item(item: dict) -> dict:
    title = item["title"]
    return {**item, "type": classify_type(title), "company": find_company(title),
            "regions": find_regions(title), "skills": extract_skills_from_text(title)[0],
            "ai": bool(_AI.search(title))}


def skills_in_news(items: list[dict]) -> Counter:
    return Counter(s for it in items for s in it.get("skills", []))


def time_ago(dt: datetime | None, now: datetime | None = None) -> str:
    if dt is None:
        return ""
    secs = int(((now or datetime.now(timezone.utc)) - dt).total_seconds())
    if secs < 3600:
        return f"{max(secs // 60, 1)} min ago"
    if secs < 86400:
        return f"{secs // 3600} h ago"
    return f"{secs // 86400} d ago"


# ───────────────────────────── Grok (xAI) ────────────────────────────

XAI_BASE_URL = "https://api.x.ai/v1"
XAI_DEFAULT_MODEL = "grok-4.7"   # override with XAI_MODEL in secrets/env; model names change over time
_GROK_SYSTEM = (
    "You are a careful industry analyst for engineering students. Search the web for current information. "
    "Report only facts you can source. For every item give the date, the company, what happened (with numbers "
    "if reported), the region, and the source. If something can't be verified, say 'not verified'. "
    "End with 3 short takeaways about which technical skills matter most right now."
)


def build_grok_payload(prompt: str, model: str = XAI_DEFAULT_MODEL) -> dict:
    return {"model": model,
            "input": [{"role": "system", "content": _GROK_SYSTEM}, {"role": "user", "content": prompt}],
            "tools": [{"type": "web_search"}]}


def parse_grok_response(data: dict) -> dict:
    """Extract answer text, cited sources, and whether a live search really ran."""
    text = data.get("output_text") if isinstance(data.get("output_text"), str) else ""
    sources, searched, parts = [], False, []
    for item in data.get("output", []) or []:
        kind = item.get("type", "")
        if "search" in kind and kind != "message":
            searched = True
        if kind == "message":
            for c in item.get("content", []) or []:
                if c.get("type") == "output_text":
                    parts.append(c.get("text", ""))
                for a in c.get("annotations", []) or []:
                    if a.get("type") == "url_citation" and a.get("url"):
                        sources.append({"title": a.get("title") or a["url"], "url": a["url"]})
    seen, uniq = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            uniq.append(s)
    return {"text": text or "\n\n".join(parts), "sources": uniq, "searched": searched}


def grok_briefing(api_key: str, prompt: str, model: str = XAI_DEFAULT_MODEL, base_url: str = XAI_BASE_URL,
                  timeout: float = 120.0, post=None) -> dict:
    """Ask Grok for a web-grounded briefing. Raises with messages that never contain the key."""
    if not api_key or not api_key.strip():
        raise ValueError("No xAI API key provided.")
    if post is None:
        import requests
        post = requests.post
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    try:
        resp = post(base_url.rstrip("/") + "/responses", headers=headers,
                    json=build_grok_payload(prompt, model), timeout=timeout)
    except Exception as exc:
        raise RuntimeError(f"Couldn't reach the xAI API ({type(exc).__name__}).") from None
    code = getattr(resp, "status_code", 0)
    if code in (401, 403):
        raise PermissionError("xAI rejected the API key (check it is correct and has access to this model).")
    if code == 404:
        raise RuntimeError(f"xAI doesn't know the model '{model}'. Set XAI_MODEL to a current Grok model name.")
    if code == 429:
        raise RuntimeError("xAI rate limit or credit limit reached. Try again later.")
    if code >= 400:
        raise RuntimeError(f"xAI returned an error (HTTP {code}).")
    try:
        result = parse_grok_response(resp.json())
    except ValueError:
        raise RuntimeError("xAI returned an unreadable response.") from None
    if not result["text"]:
        raise RuntimeError("Grok returned an empty answer.")
    return result
