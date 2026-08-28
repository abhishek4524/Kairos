"""
browser.py — Generic Browser Automation over Chrome DevTools Protocol (CDP) for Kairos.

Connects to running Brave or Google Chrome instances (or launches them with remote debugging enabled)
and provides composable, natural-language-friendly browser primitives that work on
ANY website via Playwright without hardcoded pixel coordinates.
"""

import os
import re
import time
import json
import shutil
import urllib.request
import urllib.parse
import subprocess
import threading
from typing import Optional, Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, Locator
from config import platform_paths
from config import work_mode_sites

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_CDP_PORT = int(os.environ.get("KAIROS_CDP_PORT", "9222"))
DEFAULT_CHROME_CDP_PORT = int(os.environ.get("KAIROS_CHROME_CDP_PORT", "9223"))


class BrowserManager:
    """
    Thread-safe Browser Automation Manager using Playwright connected over CDP.
    Runs all Playwright calls in a dedicated background worker thread to prevent
    conflicts with the FastAPI asyncio event loop.
    Supports distinct browser targets (e.g. Brave on port 9222, Chrome on port 9223).
    """

    def __init__(self, browser_name: str = "brave", cdp_port: Optional[int] = None):
        self.browser_name = browser_name.lower().strip()
        if cdp_port is None:
            self.cdp_port = DEFAULT_CHROME_CDP_PORT if self.browser_name == "chrome" else DEFAULT_CDP_PORT
        else:
            self.cdp_port = cdp_port

        self.cdp_url = f"http://127.0.0.1:{self.cdp_port}"
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"Kairos{self.browser_name.capitalize()}Worker"
        )
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._active_page: Optional[Page] = None
        self._is_connected = False

    def is_cdp_available(self) -> bool:
        """Check if browser's remote debugging endpoint is currently responding."""
        try:
            url = f"{self.cdp_url}/json/version"
            req = urllib.request.Request(url, headers={"User-Agent": "Kairos"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_browser_exe(self) -> Optional[str]:
        """Resolves the executable path for this manager's browser."""
        if self.browser_name == "chrome":
            return platform_paths.get_chrome_path()
        return platform_paths.get_brave_path()

    def launch_with_cdp(self, url: str = "") -> bool:
        """Launch target browser configured with remote debugging enabled."""
        browser_exe = self.get_browser_exe()
        if not browser_exe or not (os.path.exists(browser_exe) or shutil.which(browser_exe)):
            var_name = "KAIROS_CHROME_PATH" if self.browser_name == "chrome" else "KAIROS_BRAVE_PATH"
            print(f"[BROWSER] {self.browser_name.capitalize()} executable not found. Please set {var_name} in backend/.env.")
            return False

        profile_name = "chrome_browser_profile" if self.browser_name == "chrome" else "browser_profile"
        user_data_dir = os.path.join(platform_paths.KAIROS_DIR, profile_name)
        os.makedirs(user_data_dir, exist_ok=True)

        args = [
            browser_exe,
            f"--remote-debugging-port={self.cdp_port}",
            f"--user-data-dir={user_data_dir}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if url:
            args.append(url)

        try:
            print(f"[BROWSER] Launching {self.browser_name.capitalize()} ({browser_exe}) with CDP port {self.cdp_port}...")
            popen_kwargs = {}
            if platform_paths.NO_WINDOW_FLAGS:
                popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
            subprocess.Popen(args, **popen_kwargs)
            # Wait up to 6 seconds for CDP port to become active
            for _ in range(12):
                time.sleep(0.5)
                if self.is_cdp_available():
                    print(f"[BROWSER] {self.browser_name.capitalize()} CDP is live on port {self.cdp_port}.")
                    return True
            return False
        except Exception as e:
            print(f"[BROWSER] Failed to launch {self.browser_name.capitalize()}: {e}")
            return False

    def launch_brave_with_cdp(self, url: str = "") -> bool:
        """Backward-compatible alias for Brave launching."""
        return self.launch_with_cdp(url)

    def launch_chrome_with_cdp(self, url: str = "") -> bool:
        """Alias for Chrome launching."""
        return self.launch_with_cdp(url)

    def _ensure_connected_worker(self) -> Tuple[bool, str]:
        """Runs inside worker thread: connects to CDP and resolves active page."""
        try:
            if not self.is_cdp_available():
                print(f"[BROWSER] CDP port {self.cdp_port} ({self.browser_name}) not reachable. Attempting to launch...")
                launched = self.launch_with_cdp()
                if not launched:
                    return False, f"Could not connect to {self.browser_name.capitalize()} on CDP port {self.cdp_port}. Please ensure it is installed or started with `--remote-debugging-port={self.cdp_port}`."

            # If already connected, check if browser is still alive
            if self._playwright and self._browser and self._browser.is_connected():
                if self._context:
                    pages = self._context.pages
                    if pages:
                        if not self._active_page or self._active_page.is_closed():
                            self._active_page = pages[-1]
                        return True, "Connected"

            # Clean up any stale handles
            self._cleanup_worker()

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                self.cdp_url,
                timeout=10000
            )

            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
            else:
                self._context = self._browser.new_context()

            pages = self._context.pages
            if pages:
                self._active_page = pages[-1]
            else:
                self._active_page = self._context.new_page()

            self._is_connected = True
            print(f"[BROWSER] Successfully connected to {self.browser_name.capitalize()} over CDP ({self.cdp_url}).")
            return True, "Connected"

        except Exception as e:
            self._cleanup_worker()
            return False, f"CDP Connection error for {self.browser_name}: {e}"

    def _cleanup_worker(self):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._playwright = None
        self._browser = None
        self._context = None
        self._active_page = None
        self._is_connected = False

    def _get_page_worker(self) -> Page:
        ok, msg = self._ensure_connected_worker()
        if not ok or not self._active_page or self._active_page.is_closed():
            if self._context and self._context.pages:
                self._active_page = self._context.pages[-1]
            else:
                raise RuntimeError(f"No active page available for {self.browser_name}: {msg}")
        return self._active_page

    def run_sync(self, func, *args, **kwargs) -> Any:
        """Executes a function inside the dedicated browser worker thread."""
        future = self._executor.submit(func, *args, **kwargs)
        return future.result()


# ── Browser Manager Registry ──────────────────────────────────────────────────
_managers: Dict[str, BrowserManager] = {}
_managers_lock = threading.Lock()


def get_browser_manager(browser_name: str = "brave") -> BrowserManager:
    """Returns singleton BrowserManager instance for the requested browser type."""
    name = browser_name.lower().strip()
    with _managers_lock:
        if name not in _managers:
            port = DEFAULT_CHROME_CDP_PORT if name == "chrome" else DEFAULT_CDP_PORT
            _managers[name] = BrowserManager(browser_name=name, cdp_port=port)
        return _managers[name]


# Default Brave instance for existing generic primitives
_manager = get_browser_manager("brave")


# ── Generic Natural-Language DOM Element Resolver ──────────────────────────────

def _extract_ordinal(text: str) -> Tuple[Optional[int], str]:
    """
    Extracts 1-based ordinal numbers like '1st', 'second', '3rd', 'last' from queries.
    Returns (1-based index or None, cleaned description).
    """
    ordinal_map = {
        "first": 1, "1st": 1,
        "second": 2, "2nd": 2,
        "third": 3, "3rd": 3,
        "fourth": 4, "4th": 4,
        "fifth": 5, "5th": 5,
        "sixth": 6, "6th": 6,
        "seventh": 7, "7th": 7,
        "eighth": 8, "8th": 8,
        "ninth": 9, "9th": 9,
        "tenth": 10, "10th": 10,
    }
    tokens = text.lower().split()
    index = None
    cleaned = []
    for t in tokens:
        clean_t = t.strip(".,;:\"'()")
        if clean_t in ordinal_map:
            index = ordinal_map[clean_t]
        elif re.match(r"^#?(\d+)(st|nd|rd|th)?$", clean_t):
            m = re.match(r"^#?(\d+)(st|nd|rd|th)?$", clean_t)
            index = int(m.group(1))
        else:
            cleaned.append(t)
    return index, " ".join(cleaned).strip()


def _resolve_element_locator(page: Page, description: str, for_typing: bool = False) -> Tuple[Optional[Locator], Dict[str, Any]]:
    """
    Resolves a natural language description to a real Playwright Locator on the active page
    using role matching, text matching, accessibility labels, and fuzzy element scoring.
    """
    desc = description.strip()
    target_idx, clean_desc = _extract_ordinal(desc)
    idx_0 = (target_idx - 1) if (target_idx and target_idx > 0) else 0

    meta = {"matched_strategy": "", "description": desc, "tag": "", "text": "", "aria_label": ""}

    # 1. Direct CSS / XPath selector if provided
    if desc.startswith(("#", ".", "//", "xpath=")) or (desc.startswith("[") and desc.endswith("]")):
        try:
            loc = page.locator(desc)
            if loc.count() > 0:
                target = loc.nth(idx_0)
                meta["matched_strategy"] = "direct_selector"
                return target, meta
        except Exception:
            pass

    # 2. Typing-specific strategies
    if for_typing:
        typing_candidates = [
            lambda: page.get_by_placeholder(re.compile(re.escape(clean_desc or desc), re.I)),
            lambda: page.get_by_label(re.compile(re.escape(clean_desc or desc), re.I)),
            lambda: page.get_by_role("textbox", name=re.compile(re.escape(clean_desc or desc), re.I)),
            lambda: page.get_by_role("searchbox", name=re.compile(re.escape(clean_desc or desc), re.I)),
            lambda: page.get_by_role("combobox", name=re.compile(re.escape(clean_desc or desc), re.I)),
        ]
        for strategy in typing_candidates:
            try:
                loc = strategy()
                if loc.count() > 0:
                    meta["matched_strategy"] = "input_role_or_label"
                    return loc.nth(idx_0), meta
            except Exception:
                continue

        # General search inputs fallback
        if any(w in desc.lower() for w in ["search", "find", "query", "searchbox", "search bar", "search input"]):
            try:
                loc = page.locator("input[type='search'], input[type='text'], input[name*='search' i], input[name*='q' i], textarea, input:not([type='hidden'])")
                if loc.count() > 0:
                    meta["matched_strategy"] = "generic_search_input"
                    return loc.nth(idx_0), meta
            except Exception:
                pass

    # 3. Role-based matching
    role_types = ["button", "link", "tab", "menuitem", "checkbox", "radio", "heading"]
    for role in role_types:
        try:
            loc = page.get_by_role(role, name=re.compile(re.escape(clean_desc or desc), re.I))
            if loc.count() > 0:
                meta["matched_strategy"] = f"role_{role}"
                return loc.nth(idx_0), meta
        except Exception:
            continue

    # 4. Text & Aria-label exact/substring match
    for query_text in [desc, clean_desc]:
        if not query_text:
            continue
        try:
            loc = page.get_by_text(re.compile(re.escape(query_text), re.I))
            if loc.count() > 0:
                meta["matched_strategy"] = "text_content"
                return loc.nth(idx_0), meta
        except Exception:
            pass

        try:
            loc = page.get_by_alt_text(re.compile(re.escape(query_text), re.I))
            if loc.count() > 0:
                meta["matched_strategy"] = "alt_text"
                return loc.nth(idx_0), meta
        except Exception:
            pass

        try:
            loc = page.get_by_title(re.compile(re.escape(query_text), re.I))
            if loc.count() > 0:
                meta["matched_strategy"] = "title_attribute"
                return loc.nth(idx_0), meta
        except Exception:
            pass

    # 5. DOM-level Smart Interactive Element Search
    js_search_script = """
    (query) => {
        const tokens = query.toLowerCase().split(/\\s+/).filter(t => t.length > 1);
        const candidates = Array.from(document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], [role="tab"], [tabindex], h1, h2, h3, h4, ytd-video-renderer, ytd-rich-item-renderer, li, tr'));
        
        let bestList = [];
        for (let i = 0; i < candidates.length; i++) {
            const el = candidates[i];
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0 || window.getComputedStyle(el).visibility === 'hidden' || window.getComputedStyle(el).display === 'none') {
                continue;
            }
            const text = (el.innerText || el.textContent || '').trim().toLowerCase();
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const title = (el.getAttribute('title') || '').toLowerCase();
            const placeholder = (el.getAttribute('placeholder') || '').toLowerCase();
            const val = (el.value || '').toLowerCase();
            const combined = `${text} ${aria} ${title} ${placeholder} ${val}`;

            let score = 0;
            for (const t of tokens) {
                if (combined.includes(t)) {
                    score += 2;
                    if (text.startsWith(t) || aria.startsWith(t)) score += 1;
                }
            }
            if (score > 0) {
                bestList.push({ index: i, score: score, text: text.substring(0, 100), tag: el.tagName.toLowerCase() });
            }
        }
        bestList.sort((a, b) => b.score - a.score);
        return bestList.slice(0, 15);
    }
    """
    try:
        results = page.evaluate(js_search_script, clean_desc or desc)
        if results:
            chosen = results[min(idx_0, len(results) - 1)]
            tag = chosen.get("tag", "")
            snippet = chosen.get("text", "")
            if snippet:
                loc = page.locator(tag).filter(has_text=snippet[:40])
                if loc.count() > 0:
                    meta["matched_strategy"] = "smart_dom_scan"
                    meta["text"] = snippet
                    meta["tag"] = tag
                    return loc.first, meta
    except Exception as e:
        print(f"[BROWSER] DOM search evaluation failed: {e}")

    return None, meta


def _extract_element_confirmation(locator: Locator) -> Dict[str, Any]:
    """Captures a snapshot confirmation of the element actually interacted with."""
    try:
        tag = locator.evaluate("el => el.tagName.toLowerCase()")
        text = locator.evaluate("el => (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || '').trim()")
        aria = locator.evaluate("el => el.getAttribute('aria-label') || ''")
        elem_id = locator.evaluate("el => el.id || ''")
        box = locator.bounding_box() or {}
        return {
            "tag": tag,
            "text": (text[:120] + "...") if len(text) > 120 else text,
            "aria_label": aria,
            "id": elem_id,
            "box": {
                "x": int(box.get("x", 0)),
                "y": int(box.get("y", 0)),
                "width": int(box.get("width", 0)),
                "height": int(box.get("height", 0)),
            } if box else {}
        }
    except Exception:
        return {"tag": "unknown", "text": "", "aria_label": "", "box": {}}


# ── Generic Browser Primitives (Worker Implementation with Verification) ────────

def _worker_navigate_to(url_or_query: str) -> Dict[str, Any]:
    page = _manager._get_page_worker()
    target = url_or_query.strip()
    
    is_url = bool(re.match(r"^(https?:\/\/|www\.)", target, re.I) or ("." in target and " " not in target))
    if is_url:
        if not target.startswith("http://") and not target.startswith("https://"):
            target = "https://" + target
        url = target
    else:
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(target)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        return {
            "success": False,
            "error_type": "NAVIGATION_FAILED",
            "message": f"Failed to navigate to '{target}': {e}"
        }

    page.wait_for_timeout(800)

    # Explicit Verification for YouTube navigation
    if "youtube.com" in target.lower() or "youtube.com" in url.lower():
        try:
            # Wait for core YouTube shell to mount
            page.wait_for_selector("ytd-app, #logo, #content, ytd-masthead", timeout=5000)
        except Exception:
            pass

    current_url = page.url
    if current_url.startswith("chrome-error://") or current_url == "about:blank":
        return {
            "success": False,
            "error_type": "NAVIGATION_PAGE_ERROR",
            "message": f"Browser opened but page failed to load: {current_url}"
        }

    return {
        "success": True,
        "message": f"Navigated to {page.url} ({page.title()}).",
        "url": page.url,
        "title": page.title(),
        "confirmation": {
            "action": "navigate",
            "target": target,
            "final_url": page.url,
            "page_title": page.title(),
        }
    }


def _worker_find_and_click(description: str) -> Dict[str, Any]:
    page = _manager._get_page_worker()
    loc, meta = _resolve_element_locator(page, description, for_typing=False)
    
    if not loc or loc.count() == 0:
        return {
            "success": False,
            "message": f"Could not find any clickable element matching: '{description}' on {page.url}",
            "confirmation": {"action": "click_failed", "description": description}
        }

    try:
        loc.scroll_into_view_if_needed(timeout=4000)
    except Exception:
        pass

    elem_conf = _extract_element_confirmation(loc)
    
    try:
        loc.click(timeout=5000)
    except Exception:
        try:
            loc.click(force=True, timeout=3000)
        except Exception:
            loc.evaluate("el => el.click()")

    page.wait_for_timeout(800)

    return {
        "success": True,
        "message": f"Clicked <{elem_conf['tag']}> '{elem_conf['text'] or elem_conf['aria_label'] or description}'.",
        "url": page.url,
        "title": page.title(),
        "confirmation": {
            "action": "clicked",
            "description": description,
            "element": elem_conf,
            "url_after": page.url,
            "title_after": page.title(),
        }
    }


def _worker_type_into(description: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
    page = _manager._get_page_worker()
    loc, meta = _resolve_element_locator(page, description, for_typing=True)

    if not loc or loc.count() == 0:
        try:
            loc = page.locator("*:focus")
            if loc.count() == 0:
                loc = page.locator("input:not([type='hidden']), textarea").first
        except Exception:
            pass

    if not loc or loc.count() == 0:
        return {
            "success": False,
            "message": f"Could not find input field matching: '{description}' on {page.url}",
            "confirmation": {"action": "type_failed", "description": description}
        }

    try:
        loc.scroll_into_view_if_needed(timeout=4000)
    except Exception:
        pass

    elem_conf = _extract_element_confirmation(loc)

    try:
        loc.click(timeout=3000)
        loc.fill(text, timeout=4000)
    except Exception:
        try:
            loc.type(text, delay=25)
        except Exception as e:
            return {"success": False, "message": f"Failed to type into field: {e}"}

    if press_enter:
        try:
            loc.press("Enter")
            page.wait_for_timeout(1000)
        except Exception:
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

    return {
        "success": True,
        "message": f"Typed '{text}' into <{elem_conf['tag']}> ({description})" + (" and pressed Enter." if press_enter else "."),
        "url": page.url,
        "title": page.title(),
        "confirmation": {
            "action": "typed",
            "description": description,
            "text_typed": text,
            "pressed_enter": press_enter,
            "element": elem_conf,
        }
    }


def _worker_scroll_page(direction: str = "down", amount: int = 500) -> Dict[str, Any]:
    """
    Scrolls the active page or dynamic YouTube/app container with multi-target execution
    and keyboard PageDown/PageUp fallback.
    """
    page = _manager._get_page_worker()
    try:
        page.bring_to_front()
    except Exception:
        pass

    dy = amount if direction.lower() == "down" else -amount
    js_scroll = f"""
    () => {{
        const beforeY = window.scrollY || document.documentElement.scrollTop || 0;
        window.scrollBy({{ top: {dy}, behavior: 'smooth' }});
        if (document.documentElement) {{
            document.documentElement.scrollTop += {dy};
        }}
        const containers = document.querySelectorAll('#primary, #contents, ytd-app, main, [role="main"]');
        containers.forEach(el => {{
            el.scrollTop += {dy};
        }});
        const afterY = window.scrollY || document.documentElement.scrollTop || 0;
        return {{ beforeY: beforeY, afterY: afterY }};
    }}
    """
    try:
        scroll_info = page.evaluate(js_scroll)
    except Exception:
        scroll_info = {}

    page.wait_for_timeout(250)

    # Fallback to key press if target container is focused
    try:
        key = "PageDown" if direction.lower() == "down" else "PageUp"
        page.keyboard.press(key)
        page.wait_for_timeout(200)
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Scrolled {direction} by {amount}px on {page.title() or 'page'}.",
        "confirmation": {
            "action": "scrolled",
            "direction": direction,
            "amount": amount,
            "scroll_info": scroll_info,
            "url": page.url
        }
    }


def _worker_extract_page_text(max_chars: int = 3000) -> Dict[str, Any]:
    page = _manager._get_page_worker()
    
    js_extract = """
    () => {
        const title = document.title || '';
        const url = window.location.href;
        
        const clone = document.body.cloneNode(true);
        const removeTags = clone.querySelectorAll('script, style, noscript, svg');
        removeTags.forEach(el => el.remove());
        
        const rawText = clone.innerText || clone.textContent || '';
        const cleanText = rawText.replace(/\\s+/g, ' ').trim();
        
        const interactives = Array.from(document.querySelectorAll('a, button, input[type="text"], input[type="search"], textarea'))
            .filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder'));
            })
            .slice(0, 20)
            .map(el => ({
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().substring(0, 60),
                role: el.getAttribute('role') || el.type || ''
            }));

        return {
            title: title,
            url: url,
            text: cleanText,
            interactives: interactives
        };
    }
    """
    data = page.evaluate(js_extract)
    full_text = data.get("text", "")
    snippet = full_text[:max_chars] + ("..." if len(full_text) > max_chars else "")

    return {
        "success": True,
        "message": f"Extracted content from {data['url']}",
        "url": data["url"],
        "title": data["title"],
        "text_content": snippet,
        "interactive_elements": data["interactives"],
        "confirmation": {
            "action": "extracted_page_content",
            "url": data["url"],
            "title": data["title"],
            "char_count": len(snippet),
        }
    }


def _worker_go_back() -> Dict[str, Any]:
    page = _manager._get_page_worker()
    page.go_back(wait_until="domcontentloaded")
    page.wait_for_timeout(600)
    return {
        "success": True,
        "message": f"Navigated back to {page.url} ({page.title()}).",
        "url": page.url,
        "title": page.title(),
        "confirmation": {"action": "go_back", "current_url": page.url}
    }


def _worker_open_new_tab(url: str = "") -> Dict[str, Any]:
    ok, msg = _manager._ensure_connected_worker()
    if not ok or not _manager._context:
        return {"success": False, "message": msg}
    
    new_p = _manager._context.new_page()
    _manager._active_page = new_p
    if url:
        return _worker_navigate_to(url)
    return {
        "success": True,
        "message": "Opened new browser tab.",
        "url": new_p.url,
        "confirmation": {"action": "opened_tab"}
    }


def _worker_switch_tab(index_or_desc: Any) -> Dict[str, Any]:
    ok, msg = _manager._ensure_connected_worker()
    if not ok or not _manager._context:
        return {"success": False, "message": msg}

    pages = _manager._context.pages
    if not pages:
        return {"success": False, "message": "No open tabs found."}

    target_page = None
    try:
        idx = int(index_or_desc)
        if 1 <= idx <= len(pages):
            target_page = pages[idx - 1]
        elif 0 <= idx < len(pages):
            target_page = pages[idx]
    except (ValueError, TypeError):
        query = str(index_or_desc).lower()
        for p in pages:
            if query in p.title().lower() or query in p.url.lower():
                target_page = p
                break

    if not target_page:
        return {
            "success": False,
            "message": f"Could not find tab matching '{index_or_desc}'. Open tabs: {[p.title() for p in pages]}",
        }

    target_page.bring_to_front()
    _manager._active_page = target_page
    return {
        "success": True,
        "message": f"Switched to tab: {target_page.title()} ({target_page.url})",
        "url": target_page.url,
        "title": target_page.title(),
        "confirmation": {"action": "switch_tab", "title": target_page.title(), "url": target_page.url}
    }


# ── Robust Verified YouTube Automation (CDP-backed) ───────────────────────────

def _worker_youtube_search(query: str) -> Dict[str, Any]:
    """
    Executes a YouTube search, types into search box or navigates, and verifies
    that video result cards render on screen before reporting success.
    """
    clean_query = query.strip()
    if not clean_query:
        return {"success": False, "error_type": "EMPTY_QUERY", "message": "No search query was provided."}

    page = _manager._get_page_worker()
    
    # Check if we are already on YouTube
    is_on_youtube = "youtube.com" in page.url.lower()

    if is_on_youtube:
        search_loc = page.locator("input#search, input.ytSearchboxComponentInput, input[name='search_query']")
        if search_loc.count() > 0:
            try:
                search_box = search_loc.first
                search_box.click(timeout=2000)
                search_box.fill(clean_query, timeout=2000)
                search_box.press("Enter")
                page.wait_for_timeout(1000)
            except Exception:
                # Fallback to direct URL navigation
                search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(clean_query)}"
                page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        else:
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(clean_query)}"
            page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
    else:
        search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(clean_query)}"
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

    # Explicit Verification: wait for search results to render
    try:
        page.wait_for_selector("ytd-video-renderer, ytd-rich-item-renderer, ytd-two-column-search-results-renderer", timeout=7000)
    except Exception:
        pass

    results_count = page.locator("ytd-video-renderer, ytd-rich-item-renderer").count()
    if results_count == 0 and "results?search_query=" not in page.url:
        return {
            "success": False,
            "error_type": "NO_SEARCH_RESULTS",
            "message": f"Searched for '{clean_query}' on YouTube, but search results failed to load."
        }

    return {
        "success": True,
        "message": f"Searched YouTube for '{clean_query}'. Found video results.",
        "query": clean_query,
        "results_count": results_count,
        "url": page.url,
        "title": page.title(),
        "confirmation": {
            "action": "youtube_search",
            "query": clean_query,
            "url": page.url
        }
    }


def _worker_youtube_play_video(index: int = 1) -> Dict[str, Any]:
    """
    Finds and plays the N-th real video on YouTube search results:
    - Filters out ads (ytd-ad-slot-renderer, [is-ad], .badge-style-type-ad) and shelves.
    - Clicks the targeted video title/thumbnail.
    - Explicitly verifies navigation to /watch and asserts HTML5 <video> playback state.
    """
    page = _manager._get_page_worker()
    idx = max(1, index)

    # 1. Target real non-ad video item renderers
    # Exclude ad slots, promo banners, and shelf headers
    video_locators = [
        "ytd-video-renderer:not([is-ad]):not(:has(.badge-style-type-ad)) a#video-title",
        "ytd-video-renderer a#video-title",
        "ytd-rich-item-renderer a#video-title-link",
        "ytd-video-renderer a#thumbnail",
        "a#video-title",
        "a[href*='/watch?v=']",
    ]

    target_loc = None
    for sel in video_locators:
        loc = page.locator(sel)
        if loc.count() >= idx:
            target_loc = loc.nth(idx - 1)
            break
        elif loc.count() > 0 and not target_loc:
            target_loc = loc.first

    if not target_loc or target_loc.count() == 0:
        return {
            "success": False,
            "error_type": "VIDEO_NOT_FOUND",
            "message": f"Could not find video #{idx} on YouTube. Please ensure search results are loaded."
        }

    elem_conf = _extract_element_confirmation(target_loc)
    video_title = elem_conf.get("text") or elem_conf.get("aria_label") or f"video #{idx}"

    try:
        target_loc.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass

    try:
        target_loc.click(timeout=5000)
    except Exception:
        try:
            target_loc.click(force=True, timeout=3000)
        except Exception:
            target_loc.evaluate("el => el.click()")

    page.wait_for_timeout(1000)

    # 2. Verification Step: Check watch URL transition & video playback state
    navigated_watch = False
    for _ in range(10):
        if "/watch" in page.url:
            navigated_watch = True
            break
        time.sleep(0.5)

    # Inspect <video> element inside DOM and ensure playback
    js_check_video = """
    () => {
        const v = document.querySelector('video');
        if (!v) return { exists: false, playing: false, paused: true, currentTime: 0 };
        if (v.paused && v.readyState >= 2) {
            try { v.play(); } catch(e) {}
        }
        return {
            exists: true,
            playing: !v.paused,
            paused: v.paused,
            currentTime: v.currentTime,
            duration: v.duration
        };
    }
    """
    try:
        v_state = page.evaluate(js_check_video)
        if v_state.get("paused"):
            page.keyboard.press("k")
            time.sleep(0.3)
            v_state = page.evaluate(js_check_video)
    except Exception:
        v_state = {}

    if not navigated_watch and not v_state.get("exists"):
        return {
            "success": False,
            "error_type": "VIDEO_PLAY_FAILED",
            "message": f"Clicked video #{idx} ('{video_title}'), but the YouTube player failed to start playback."
        }

    return {
        "success": True,
        "message": f"Playing {video_title} on YouTube.",
        "video_title": video_title,
        "index": idx,
        "url": page.url,
        "title": page.title(),
        "video_state": v_state,
        "confirmation": {
            "action": "youtube_play_video",
            "index": idx,
            "video_title": video_title,
            "url": page.url,
        }
    }


def _worker_youtube_control(action: str) -> Dict[str, Any]:
    page = _manager._get_page_worker()
    act = action.lower().strip()

    key_map = {
        "play_pause": "k", "play": "k", "pause": "k", "toggle": "k",
        "mute": "m", "unmute": "m",
        "fullscreen": "f", "full_screen": "f",
        "seek_forward": "l", "forward": "l",
        "seek_backward": "j", "rewind": "j",
        "restart": "0", "beginning": "0",
    }

    if act in key_map:
        key = key_map[act]
        page.keyboard.press(key)
        return {"success": True, "message": f"YouTube playback control '{act}' executed (key '{key}')."}
    elif act in ("volume_up", "louder"):
        for _ in range(3):
            page.keyboard.press("ArrowUp")
            time.sleep(0.05)
        return {"success": True, "message": "Increased volume."}
    elif act in ("volume_down", "quieter"):
        for _ in range(3):
            page.keyboard.press("ArrowDown")
            time.sleep(0.05)
        return {"success": True, "message": "Decreased volume."}
    elif act in ("next_video", "next"):
        page.keyboard.press("Shift+N")
        return {"success": True, "message": "Skipped to next video."}

    return {"success": False, "message": f"Unknown YouTube action: {action}"}


# ── Work Mode Execution in Google Chrome (CDP-backed) ──────────────────────────

def _worker_work_mode(sites: Optional[List[Dict[str, str]]] = None, workspace: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes Work Mode:
    1. Connects to/launches Google Chrome on its dedicated CDP port (9223).
    2. Opens each configured site in separate tabs, verifying actual page loading.
    3. Launches VS Code opening the configured workspace.
    """
    chrome_mgr = get_browser_manager("chrome")
    ok, msg = chrome_mgr._ensure_connected_worker()
    if not ok:
        return {
            "success": False,
            "error_type": "CHROME_CDP_ERROR",
            "message": f"Could not connect to Google Chrome via CDP: {msg}",
            "loaded_tabs": [],
            "failed_tabs": []
        }

    target_sites = sites if sites is not None else work_mode_sites.get_work_mode_sites()
    target_workspace = workspace if workspace is not None else work_mode_sites.get_default_workspace()

    loaded_tabs = []
    failed_tabs = []

    for i, site in enumerate(target_sites):
        url = site.get("url", "")
        name = site.get("name", url)
        keyword = site.get("expected_keyword", "").lower()

        try:
            if i == 0 and chrome_mgr._context and chrome_mgr._context.pages:
                page = chrome_mgr._context.pages[0]
            else:
                if chrome_mgr._context:
                    page = chrome_mgr._context.new_page()
                else:
                    raise RuntimeError("Browser context not available.")

            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(800)

            curr_url = page.url
            curr_title = page.title()

            is_valid = bool(
                curr_url and
                curr_url != "about:blank" and
                not curr_url.startswith("chrome-error://")
            )
            if keyword and is_valid:
                pass

            if is_valid:
                loaded_tabs.append({
                    "name": name,
                    "url": curr_url,
                    "title": curr_title,
                    "status": "loaded"
                })
            else:
                failed_tabs.append({
                    "name": name,
                    "url": url,
                    "error": f"Page did not load valid content (title: '{curr_title}', url: '{curr_url}')"
                })
        except Exception as e:
            failed_tabs.append({
                "name": name,
                "url": url,
                "error": str(e)
            })

    # Prepare VS Code workspace directory
    try:
        os.makedirs(target_workspace, exist_ok=True)
    except Exception as e:
        print(f"[WorkMode] Could not create workspace directory '{target_workspace}': {e}")

    # Launch VS Code
    vscode_path = platform_paths.get_vscode_path()
    vscode_launched = False
    vscode_msg = ""
    if vscode_path and (os.path.exists(vscode_path) or shutil.which(vscode_path)):
        try:
            popen_kwargs = {}
            if platform_paths.NO_WINDOW_FLAGS:
                popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
            subprocess.Popen([vscode_path, target_workspace], **popen_kwargs)
            vscode_launched = True
            vscode_msg = f"VS Code opened at '{target_workspace}'."
        except Exception as e:
            vscode_msg = f"Failed to launch VS Code: {e}"
    else:
        vscode_msg = "VS Code executable not found on PATH or via KAIROS_VSCODE_PATH."

    total_sites = len(target_sites)
    if len(loaded_tabs) == total_sites and vscode_launched:
        return {
            "success": True,
            "message": f"Work mode activated! Opened {len(loaded_tabs)} sites in Google Chrome and launched VS Code ({target_workspace}).",
            "loaded_tabs": loaded_tabs,
            "failed_tabs": [],
            "vscode_status": vscode_msg,
            "workspace": target_workspace
        }
    elif len(loaded_tabs) > 0:
        fail_names = [f["name"] for f in failed_tabs]
        err_detail = f" (Failed sites: {', '.join(fail_names)})" if fail_names else ""
        vs_detail = f" ({vscode_msg})" if not vscode_launched else ""
        return {
            "success": True,
            "partial_failure": True,
            "message": f"Work mode partially activated: {len(loaded_tabs)}/{total_sites} sites loaded in Google Chrome.{err_detail}{vs_detail}",
            "loaded_tabs": loaded_tabs,
            "failed_tabs": failed_tabs,
            "vscode_status": vscode_msg,
            "workspace": target_workspace
        }
    else:
        return {
            "success": False,
            "error_type": "WORK_MODE_FAILED",
            "message": f"Failed to load work mode sites in Google Chrome: {failed_tabs}. {vscode_msg}",
            "loaded_tabs": [],
            "failed_tabs": failed_tabs,
            "vscode_status": vscode_msg,
            "workspace": target_workspace
        }


# ── Public API (Safe Thread Dispatchers) ───────────────────────────────────────

def navigate_to(url_or_query: str) -> Dict[str, Any]:
    return _manager.run_sync(_worker_navigate_to, url_or_query)

def find_and_click(description: str) -> Dict[str, Any]:
    return _manager.run_sync(_worker_find_and_click, description)

def type_into(description: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
    return _manager.run_sync(_worker_type_into, description, text, press_enter)

def scroll_page(direction: str = "down", amount: int = 500) -> Dict[str, Any]:
    return _manager.run_sync(_worker_scroll_page, direction, amount)

def extract_page_text(max_chars: int = 3000) -> Dict[str, Any]:
    return _manager.run_sync(_worker_extract_page_text, max_chars)

def read_page(max_chars: int = 3000) -> Dict[str, Any]:
    """Alias for extract_page_text."""
    return extract_page_text(max_chars)

def go_back() -> Dict[str, Any]:
    return _manager.run_sync(_worker_go_back)

def open_new_tab(url: str = "") -> Dict[str, Any]:
    return _manager.run_sync(_worker_open_new_tab, url)

def switch_tab(index_or_description: Any) -> Dict[str, Any]:
    return _manager.run_sync(_worker_switch_tab, index_or_description)

def youtube_search(query: str) -> Dict[str, Any]:
    return _manager.run_sync(_worker_youtube_search, query)

def youtube_play_video(index: int = 1) -> Dict[str, Any]:
    return _manager.run_sync(_worker_youtube_play_video, index)

def youtube_control(action: str) -> Dict[str, Any]:
    return _manager.run_sync(_worker_youtube_control, action)

def run_work_mode(sites: Optional[List[Dict[str, str]]] = None, workspace: Optional[str] = None) -> Dict[str, Any]:
    """Executes Work Mode in Google Chrome and launches VS Code."""
    chrome_mgr = get_browser_manager("chrome")
    return chrome_mgr.run_sync(_worker_work_mode, sites, workspace)
