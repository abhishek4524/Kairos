"""
info_tools.py — Live Real-Time Information, News, Date/Time & Web Search for Kairos.

Provides Jarvis-style live world intelligence:
1. `get_current_datetime` — User's local date, day of week, time & timezone.
2. `get_weather` — Live current weather for any city/location via Open-Meteo (free, no API key).
3. `get_news` — Live news for broad topics (tech, business, world) and Indian city/state queries
   (Muzaffarnagar, Uttar Pradesh, Delhi) via Google News RSS & Tavily/Serper fallback with TTL caching.
4. `answer_general_question` — Web-search-backed question answering for live events, weather, facts.
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
_WEATHER_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}

NEWS_CACHE_TTL = 300    # 5 minutes in seconds
SEARCH_CACHE_TTL = 600  # 10 minutes in seconds
WEATHER_CACHE_TTL = 600 # 10 minutes in seconds


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


# ── 2. Live Weather (Open-Meteo, free, no API key) ────────────────────────────

# WMO Weather Interpretation Codes → human-readable description
_WMO_CODES: Dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def get_weather(city: str, country: str = "") -> Dict[str, Any]:
    """
    Returns current weather for any city using Open-Meteo API (free, no API key required).

    Steps:
    1. Geocode the city name to (lat, lon) using Open-Meteo's geocoding endpoint.
    2. Fetch current weather (temperature, apparent temperature, wind speed, humidity,
       precipitation, and WMO weather code) from Open-Meteo's forecast endpoint.
    3. Return structured result with a human-readable spoken_message.

    Args:
        city: City name (e.g. "Mumbai", "London", "New York").
        country: Optional country name or ISO code to disambiguate (e.g. "India", "US").

    Returns:
        Dict with keys: success, city, country, temperature_c, feels_like_c, humidity_pct,
        wind_speed_kmh, precipitation_mm, weather_description, spoken_message, message.
    """
    cache_key = f"{city.lower().strip()}|{country.lower().strip()}"
    now_ts = time.time()
    if cache_key in _WEATHER_CACHE:
        ts, cached = _WEATHER_CACHE[cache_key]
        if now_ts - ts < WEATHER_CACHE_TTL:
            return cached

    city_clean = city.strip()
    if not city_clean:
        return {"success": False, "message": "Please provide a city name."}

    # ── Step 1: Geocode ───────────────────────────────────────────────────────
    try:
        geo_query = urllib.parse.urlencode({
            "name": city_clean,
            "count": 5,
            "language": "en",
            "format": "json",
        })
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?{geo_query}"
        geo_req = urllib.request.Request(
            geo_url,
            headers={"User-Agent": "Kairos-AI/1.0 (contact@kairos.local)"}
        )
        with urllib.request.urlopen(geo_req, timeout=6) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"success": False, "message": f"Could not reach geocoding service: {e}"}

    results = geo_data.get("results") or []
    if not results:
        return {
            "success": False,
            "message": f"Could not find a location named '{city_clean}'. Please check the city name.",
        }

    # Pick the best match: prefer country match if provided
    match = results[0]
    if country:
        country_lo = country.lower()
        for r in results:
            if country_lo in (r.get("country", "") + " " + r.get("country_code", "")).lower():
                match = r
                break

    lat = match.get("latitude")
    lon = match.get("longitude")
    resolved_city = match.get("name", city_clean)
    resolved_country = match.get("country", "")

    # ── Step 2: Fetch weather ─────────────────────────────────────────────────
    try:
        wx_params = urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,weathercode",
            "wind_speed_unit": "kmh",
            "timezone": "auto",
        })
        wx_url = f"https://api.open-meteo.com/v1/forecast?{wx_params}"
        wx_req = urllib.request.Request(
            wx_url,
            headers={"User-Agent": "Kairos-AI/1.0 (contact@kairos.local)"}
        )
        with urllib.request.urlopen(wx_req, timeout=8) as resp:
            wx_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"success": False, "message": f"Could not fetch weather data: {e}"}

    curr = wx_data.get("current", {})
    temp_c = curr.get("temperature_2m")
    feels_c = curr.get("apparent_temperature")
    humidity = curr.get("relative_humidity_2m")
    wind_kmh = curr.get("wind_speed_10m")
    precip_mm = curr.get("precipitation", 0.0)
    wmo_code = curr.get("weathercode", 0)
    description = _WMO_CODES.get(wmo_code, f"Weather code {wmo_code}")

    # Build spoken message
    location_str = f"{resolved_city}, {resolved_country}" if resolved_country else resolved_city
    spoken = (
        f"The weather in {location_str} right now is {description.lower()}. "
        f"Temperature is {temp_c}°C, feels like {feels_c}°C. "
        f"Humidity {humidity}%, wind speed {wind_kmh} km/h."
    )
    if precip_mm and precip_mm > 0:
        spoken += f" Precipitation: {precip_mm} mm."

    result = {
        "success": True,
        "city": resolved_city,
        "country": resolved_country,
        "latitude": lat,
        "longitude": lon,
        "temperature_c": temp_c,
        "feels_like_c": feels_c,
        "humidity_pct": humidity,
        "wind_speed_kmh": wind_kmh,
        "precipitation_mm": precip_mm,
        "weather_code": wmo_code,
        "weather_description": description,
        "spoken_message": spoken,
        "message": spoken,
    }
    _WEATHER_CACHE[cache_key] = (now_ts, result)
    return result


# ── 3. Live News (Hyperlocal Indian & Global Topics) ───────────────────────────


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


# ── 4. Spreadsheet Query & Analytics Tool ─────────────────────────────────────

def query_spreadsheet(doc_name: str = "", query: str = "") -> Dict[str, Any]:
    """
    Executes pandas numeric computations (sum, mean, min, max, count, stats)
    directly on ingested CSV and Excel spreadsheets.
    """
    try:
        from documents.ingestion import STORED_SPREADSHEETS
    except ImportError:
        STORED_SPREADSHEETS = {}

    if not STORED_SPREADSHEETS:
        return {
            "success": False,
            "message": "No spreadsheets (.csv / .xlsx) have been ingested yet in this session.",
            "spoken_message": "No spreadsheets have been ingested yet."
        }

    target_name = None
    target_dfs = None
    clean_target = doc_name.strip().lower()

    if clean_target:
        for name, dfs in STORED_SPREADSHEETS.items():
            if clean_target in name.lower():
                target_name = name
                target_dfs = dfs
                break

    if not target_dfs:
        target_name, target_dfs = list(STORED_SPREADSHEETS.items())[-1]

    df = list(target_dfs.values())[0] if target_dfs else None
    if df is None or df.empty:
        return {"success": False, "message": f"Spreadsheet '{target_name}' is empty."}

    clean_q = query.lower().strip()
    all_cols = list(df.columns)
    num_cols = list(df.select_dtypes(include=["number"]).columns)

    target_col = None
    for c in all_cols:
        if str(c).lower() in clean_q:
            target_col = c
            break

    if not target_col and num_cols:
        target_col = num_cols[0]

    result_text = ""
    if target_col and target_col in df.columns:
        col_series = df[target_col]
        try:
            if "sum" in clean_q or "total" in clean_q:
                val = col_series.sum()
                result_text = f"The total sum of column '{target_col}' in spreadsheet '{target_name}' is {val:,.2f}."
            elif "average" in clean_q or "mean" in clean_q or "avg" in clean_q:
                val = col_series.mean()
                result_text = f"The average value of column '{target_col}' in spreadsheet '{target_name}' is {val:,.2f}."
            elif "max" in clean_q or "highest" in clean_q or "maximum" in clean_q:
                val = col_series.max()
                result_text = f"The maximum value in column '{target_col}' in spreadsheet '{target_name}' is {val:,.2f}."
            elif "min" in clean_q or "lowest" in clean_q or "minimum" in clean_q:
                val = col_series.min()
                result_text = f"The minimum value in column '{target_col}' in spreadsheet '{target_name}' is {val:,.2f}."
            elif "count" in clean_q or "how many" in clean_q:
                val = len(df)
                result_text = f"Spreadsheet '{target_name}' contains {val} total rows."
        except Exception:
            pass

    if not result_text:
        row_count = len(df)
        cols_str = ", ".join([str(c) for c in all_cols])
        result_text = f"Spreadsheet '{target_name}' has {row_count} rows and columns: {cols_str}."

    return {
        "success": True,
        "spreadsheet": target_name,
        "query": query,
        "answer": result_text,
        "spoken_message": result_text,
        "message": result_text
    }

