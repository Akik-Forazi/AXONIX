"""
This module empowers AXONIX-ZERO with web access capabilities.
It includes utilities for retrieving website content and performing web searches
using privacy-focused engines, all without requiring external API keys.
"""

import urllib.request
import urllib.parse
import json
import re


class WebTools:
    """
    A collection of networking utilities that allow the agent to gather 
    real-time information from the internet.
    """
    # Standard identification header to ensure reliable communication with web servers.
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (AXONIX-ZERO Intelligence Agent/1.0)",
    }

    def get(self, url: str, max_chars: int = 8000) -> str:
        """
        Retrieves the textual content of a specific URL.
        Includes automatic sanitization to strip HTML boilerplate and focus on readable text.
        """
        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            # High-efficiency sanitization: removal of non-content elements.
            text = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.DOTALL)
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

            # Enforcing a safe buffer limit to prevent context overflow.
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n... (Content truncated for brevity, {len(text)} total characters)"

            return f"Retrieved Content from {url}:\n{text}"
        except Exception as e:
            return f"Error: Unable to access {url}. {e}"

    def search(self, query: str, max_results: int = 5) -> str:
        """
        Performs a web search using DuckDuckGo's lightweight interface.
        Provides a structured summary of titles, URLs, and snippets.
        """
        try:
            # Preparing the search query for the URL.
            encoded = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            req = urllib.request.Request(url, headers={**self.HEADERS, "Accept-Language": "en-US"})
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            # Parsing the search result blocks from the raw response.
            results = []
            blocks = re.findall(r'class="result__body".*?(?=class="result__body"|$)', raw, re.DOTALL)

            for block in blocks[:max_results]:
                title_m = re.search(r'class="result__a[^"]*"[^>]*>(.*?)</a>', block)
                url_m = re.search(r'href="(https?://[^"]+)"', block)
                snippet_m = re.search(r'class="result__snippet"[^>]*>(.*?)</span>', block, re.DOTALL)

                title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else "Untitled Result"
                result_url = url_m.group(1) if url_m else "No link available"
                snippet = re.sub(r"<[^>]+>", "", snippet_m.group(1)).strip() if snippet_m else "No summary available."

                results.append(f"  [{len(results)+1}] {title}\n      Source: {result_url}\n      Summary: {snippet}")

            if not results:
                return f"Intelligence Report: No relevant information found for '{query}'."

            return f"Web Search Results for '{query}':\n" + "\n\n".join(results)
        except Exception as e:
            return f"Error: Search operation failed. {e}"
