"""
Web Tools - Fetch URLs, search the web (DuckDuckGo, no API key needed)
"""

import urllib.request
import urllib.parse
import json
import re


class WebTools:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (axonix Agent/1.0)",
    }

    def get(self, url: str, max_chars: int = 8000) -> str:
        """Fetch a URL and return text content."""
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            # Strip HTML tags for readability
            text = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.DOTALL)
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) > max_chars:
                text = text[:max_chars] + f"\n... [truncated, {len(text)} total chars]"

            return f"[URL: {url}]\n{text}"
        except Exception as e:
            return f"[ERROR] Failed to fetch {url}: {e}"

    def search(self, query: str, max_results: int = 5) -> str:
        """Search the web using DuckDuckGo HTML (no API key needed)."""
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            req = urllib.request.Request(url, headers={**self.HEADERS, "Accept-Language": "en-US"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            # Extract results
            results = []
            blocks = re.findall(r'class="result__body".*?(?=class="result__body"|$)', raw, re.DOTALL)

            for block in blocks[:max_results]:
                title_m = re.search(r'class="result__a[^"]*"[^>]*>(.*?)</a>', block)
                url_m = re.search(r'href="(https?://[^"]+)"', block)
                snippet_m = re.search(r'class="result__snippet"[^>]*>(.*?)</span>', block, re.DOTALL)

                title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else "?"
                result_url = url_m.group(1) if url_m else "?"
                snippet = re.sub(r"<[^>]+>", "", snippet_m.group(1)).strip() if snippet_m else ""

                results.append(f"  [{len(results)+1}] {title}\n      {result_url}\n      {snippet}")

            if not results:
                return f"[SEARCH] No results found for: {query}"

            return f"[SEARCH: {query}]\n" + "\n\n".join(results)
        except Exception as e:
            return f"[ERROR] Search failed: {e}"
