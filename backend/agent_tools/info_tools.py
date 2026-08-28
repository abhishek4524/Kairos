"""
info_tools.py — Live Real-Time Information, News, Date/Time & Web Search for Kairos.

Provides Jarvis-style live world intelligence:
1. `get_current_datetime` — User's local date, day of week, time & timezone.
2. `get_news` — Live news for broad topics (tech, business, world) and Indian city/state queries
   (Muzaffarnagar, Uttar Pradesh, Delhi) via Google News RSS & Tavily/Serper fallback with TTL caching.
3. `answer_general_question` — Web-search-backed question answering for live events, weather, facts.
"""

import os
import re
import time
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo  # type: ignore

# ── Configuration & In-Memory TTL Cache ───────────────────────────────────────
KAIROS_SEARCH_API_KEY = os.environ.get("KAIROS_SEARCH_API_KEY", "").strip() or os.environ.get("TAVILY_API_KEY", "").strip()
KAIROS_TIMEZONE = os.environ.get("KAIROS_TIMEZONE", "").strip()

# In-memory TTL caches: {query_key: (timestamp, result_dict)}
_NEWS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_SEARCH_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

NEWS_CACHE_TTL = 300   # 5 minutes in seconds
SEARCH_CACHE_TTL = 600  # 10 minutes in seconds


def _clean_text(text: str) -> str:
    """Strips HTML tags, XML artifacts, and extra whitespace."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"&[a-zA-Z0-9#]+;", " ", clean)
    return " ".join(clean.split()).strip()


# ── 1. Date & Time Utility ───────────────────────────────────────────────────

def get_current_datetime(timezone_override: str = "") -> Dict[str, Any]:
    """
    Returns the current date, day of the week, 12-hour time, and timezone.
    Supports system local timezone detection with KAIROS_TIMEZONE / parameter override.
    """
    target_tz_str = timezone_override.strip() or os.environ.get("KAIROS_TIMEZONE", "").strip()
    tz = None

    if target_tz_str:
        try:
            tz = zoneinfo.ZoneInfo(target_tz_str)
        except Exception:
            tz = None

    if tz is None:
        # Detect local timezone from system
        try:
            tz = datetime.now().astimezone().tzinfo
        except Exception:
            tz = None

    now = datetime.now(tz) if tz else datetime.now()
    
    # Formats
    date_str = now.strftime("%B %d, %Y")           # e.g. August 27, 2026
    day_str = now.strftime("%A")                   # e.g. Thursday
    time_12 = now.strftime("%I:%M %p").lstrip("0") # e.g. 10:30 AM
    time_24 = now.strftime("%H:%M")                # e.g. 10:30
    tz_name = now.strftime("%Z") or "Local Time"   # e.g. IST, UTC, EDT

    spoken_message = f"Today is {day_str}, {date_str}, and the time is {time_12} ({tz_name})."
    
    return {
        "success": True,
        "date": date_str,
        "day": day_str,
        "time": time_12,
        "time_24h": time_24,
        "timezone": tz_name,
        "iso": now.isoformat(),
        "spoken_message": spoken_message,
        "message": spoken_message
    }


# ── 2. Live News (Hyperlocal Indian & Global Topics) ───────────────────────────

def _fetch_google_news_rss(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Queries Google News RSS with regional Indian priority.
    Returns list of dicts: [{title, link, pub_date, source}].
    """
    encoded_query = urllib.parse.quote(query.strip())
    # hl=en-IN&gl=IN&ceid=IN:en ensures outstanding Indian national & hyperlocal coverage
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        content = resp.read()
        root = ET.fromstring(content)
        items = root.findall(".//item")
        
        results = []
        for it in items[:max_results]:
            title_raw = it.find("title").text if it.find("title") is not None else ""
            link = it.find("link").text if it.find("link") is not None else ""
            pub_date = it.find("pubDate").text if it.find("pubDate") is not None else ""
            source_raw = it.find("source").text if it.find("source") is not None else ""
            
            # Google news title usually ends with ' - Source Name'
            title_clean = _clean_text(title_raw)
            if " - " in title_clean and not source_raw:
                parts = title_clean.rsplit(" - ", 1)
                headline = parts[0].strip()
                source = parts[1].strip()
            else:
                headline = title_clean
                source = source_raw or "News"

            if headline:
                results.append({
                    "title": headline,
                    "link": link,
                    "source": source,
                    "pub_date": pub_date
                })
        return results


def _fetch_tavily_news(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Fetches news using Tavily Search API if KAIROS_SEARCH_API_KEY is configured."""
    api_key = KAIROS_SEARCH_API_KEY
    if not api_key:
        return []

    url = "https://api.tavily.com/search"
    payload = json.dumps({
        "api_key": api_key,
        "query": f"{query} news today",
        "topic": "news",
        "search_depth": "basic",
        "max_results": max_results
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Kairos/1.0"}
    )
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        articles = data.get("results", [])
        results = []
        for a in articles:
            results.append({
                "title": _clean_text(a.get("title", "")),
                "link": a.get("url", ""),
                "source": urllib.parse.urlparse(a.get("url", "")).netloc.replace("www.", ""),
                "content": _clean_text(a.get("content", ""))[:180]
            })
        return results


def get_news(topic_or_location: str = "") -> Dict[str, Any]:
    """
    Fetches live news for a topic or location (e.g. 'Muzaffarnagar', 'Uttar Pradesh', 'tech news').
    Summarizes top headlines for voice TTS and returns markdown links for chat.
    Uses 5-minute in-memory TTL caching.
    """
    query = (topic_or_location or "top headlines India").strip()
    cache_key = query.lower()

    # Check TTL cache
    now_ts = time.time()
    if cache_key in _NEWS_CACHE:
        cached_ts, cached_data = _NEWS_CACHE[cache_key]
        if now_ts - cached_ts < NEWS_CACHE_TTL:
            return cached_data

    articles = []
    fetch_error = None

    # 1. Try Google News RSS (hyperlocal Indian + global support, 0-cost, live)
    try:
        articles = _fetch_google_news_rss(query, max_results=5)
    except Exception as e:
        fetch_error = str(e)

    # 2. Fallback to Tavily API if RSS failed or returned nothing
    if not articles and KAIROS_SEARCH_API_KEY:
        try:
            articles = _fetch_tavily_news(query, max_results=5)
        except Exception as e:
            fetch_error = str(e)

    if not articles:
        return {
            "success": False,
            "error_type": "NEWS_FETCH_FAILED",
            "query": query,
            "message": f"I couldn't fetch live news for '{query}' right now. Please check your network connection.",
            "spoken_message": f"I couldn't fetch live news for {query} right now."
        }

    # Construct voice-friendly concise summary (Top 3 headlines)
    top_3 = articles[:3]
    spoken_points = []
    for i, a in enumerate(top_3, 1):
        spoken_points.append(f"{a['title']} from {a['source']}.")
    
    spoken_summary = f"Here are the latest news updates for {query}: " + " Next, ".join(spoken_points)

    # Construct markdown chat text with links
    md_lines = [f"### 📰 Latest News: {query.title()}"]
    for a in articles:
        link_str = f" ([Read more]({a['link']}))" if a.get("link") else ""
        src_str = f" *— {a['source']}*" if a.get("source") else ""
        md_lines.append(f"- **{a['title']}**{src_str}{link_str}")

    chat_text = "\n".join(md_lines)

    result = {
        "success": True,
        "query": query,
        "total_results": len(articles),
        "articles": articles,
        "spoken_message": spoken_summary,
        "chat_markdown": chat_text,
        "message": spoken_summary
    }

    # Store in TTL cache
    _NEWS_CACHE[cache_key] = (now_ts, result)
    return result


# ── 3. General Knowledge / Live Web Search Q&A ────────────────────────────────

def _fetch_tavily_search(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Searches the web via Tavily Search API."""
    if not KAIROS_SEARCH_API_KEY:
        return []

    url = "https://api.tavily.com/search"
    payload = json.dumps({
        "api_key": KAIROS_SEARCH_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Kairos/1.0"}
    )
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        results = []
        for r in data.get("results", []):
            results.append({
                "title": _clean_text(r.get("title", "")),
                "snippet": _clean_text(r.get("content", "")),
                "url": r.get("url", "")
            })
        return results


def _fetch_duckduckgo_search(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    """Fallback web search using DuckDuckGo HTML parser."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
        urls = re.findall(r'<a class="result__url[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles = re.findall(r'<a class="result__title[^>]*>(.*?)</a>', html, re.DOTALL)
        
        results = []
        for i in range(min(len(snippets), max_results)):
            snippet = _clean_text(snippets[i])
            url_target = urls[i][0].strip() if i < len(urls) else ""
            title = _clean_text(titles[i]) if i < len(titles) else "Web Result"
            if snippet:
                results.append({"title": title, "snippet": snippet, "url": url_target})
        return results


def answer_general_question(query: str) -> Dict[str, Any]:
    """
    Answers general knowledge / live web queries by routing through real-time web search.
    Synthesizes a 2-4 sentence conversational answer for voice and returns markdown source links for chat.
    Uses 10-minute in-memory TTL caching.
    """
    clean_q = query.strip()
    if not clean_q:
        return {"success": False, "error_type": "EMPTY_QUERY", "message": "No question was provided."}

    cache_key = clean_q.lower()
    now_ts = time.time()
    if cache_key in _SEARCH_CACHE:
        cached_ts, cached_data = _SEARCH_CACHE[cache_key]
        if now_ts - cached_ts < SEARCH_CACHE_TTL:
            return cached_data

    search_results = []
    error_msg = None

    # 1. Try Tavily API if key exists
    if KAIROS_SEARCH_API_KEY:
        try:
            search_results = _fetch_tavily_search(clean_q, max_results=4)
        except Exception as e:
            error_msg = str(e)

    # 2. Try DuckDuckGo / Web search fallback
    if not search_results:
        try:
            search_results = _fetch_duckduckgo_search(clean_q, max_results=4)
        except Exception as e:
            error_msg = str(e)

    # 3. Try Google News search if looking for recent event / news
    if not search_results:
        try:
            rss_news = _fetch_google_news_rss(clean_q, max_results=3)
            for n in rss_news:
                search_results.append({"title": n["title"], "snippet": n["title"], "url": n["link"]})
        except Exception as e:
            error_msg = str(e)

    if not search_results:
        return {
            "success": False,
            "error_type": "SEARCH_FAILED",
            "query": clean_q,
            "message": f"I couldn't find live information for '{clean_q}' right now. Please try again in a moment.",
            "spoken_message": f"I couldn't find live information for {clean_q} right now."
        }

    # Extract snippets and synthesize concise answer
    combined_snippets = [r["snippet"] for r in search_results if r.get("snippet")]
    synthesized_answer = " ".join(combined_snippets[:2])
    if len(synthesized_answer) > 300:
        synthesized_answer = synthesized_answer[:297] + "..."

    # Markdown format with source citations
    sources_md = []
    for r in search_results:
        if r.get("url"):
            sources_md.append(f"- [{r.get('title', 'Source')}]({r.get('url')})")

    sources_text = "\n".join(sources_md) if sources_md else ""

    result = {
        "success": True,
        "query": clean_q,
        "answer": synthesized_answer,
        "sources": [r.get("url") for r in search_results if r.get("url")],
        "spoken_message": synthesized_answer,
        "chat_markdown": f"{synthesized_answer}\n\n**Sources:**\n{sources_text}" if sources_text else synthesized_answer,
        "message": synthesized_answer
    }

    _SEARCH_CACHE[cache_key] = (now_ts, result)
    return result
