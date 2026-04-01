"""
Lightweight web search bridge — no browser, no API key.
Uses DuckDuckGo HTML scraping via requests.
Fast, reliable, no Playwright needed.
"""
import sys
import json
import re
import urllib.request
import urllib.parse


def search(query: str, limit: int = 5) -> dict:
    """Search DuckDuckGo HTML for real results."""
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/html",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")

        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</span>', html)
        urls     = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html)

        results = []
        for i in range(min(limit, len(titles))):
            results.append({
                "title":   re.sub(r"<[^>]+>", "", titles[i]).strip(),
                "snippet": re.sub(r"<[^>]+>", "", snippets[i] if i < len(snippets) else "").strip(),
                "url":     urls[i].strip() if i < len(urls) else "",
                "source":  "DuckDuckGo",
            })
        return {"query": query, "results": results, "engine": "DuckDuckGo"}
    except Exception as e:
        return {"error": str(e), "query": query}


def fetch_page(url: str) -> dict:
    """Fetch a single web page content."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; jagabot/1.0)"}
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=10)
        html = response.read().decode("utf-8", errors="ignore")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return {"url": url, "content": text[:3000]}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "search"
    query  = sys.argv[2] if len(sys.argv) > 2 else "latest news"
    limit  = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    if action == "fetch":
        result = fetch_page(query)
    else:
        result = search(query, limit)

    print(json.dumps(result, ensure_ascii=False))
