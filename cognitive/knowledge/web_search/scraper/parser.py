"""HTML to Clean Markdown Converter with boilerplate and ad stripping."""

import hashlib
import html
import re
from typing import List, Tuple
from urllib.parse import urlparse
from ..core.models import ScrapedPage, utc_now


class HTMLMarkdownParser:
    """Parses raw HTML into clean, structured Markdown, stripping scripts, ads, and navigation."""

    BOILERPLATE_TAGS = [
        r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
        r"<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>",
        r"<noscript\b[^<]*(?:(?!<\/noscript>)<[^<]*)*<\/noscript>",
        r"<nav\b[^<]*(?:(?!<\/nav>)<[^<]*)*<\/nav>",
        r"<header\b[^<]*(?:(?!<\/header>)<[^<]*)*<\/header>",
        r"<footer\b[^<]*(?:(?!<\/footer>)<[^<]*)*<\/footer>",
        r"<aside\b[^<]*(?:(?!<\/aside>)<[^<]*)*<\/aside>",
        r"<svg\b[^<]*(?:(?!<\/svg>)<[^<]*)*<\/svg>",
        r"<!--.*?-->",
    ]

    @classmethod
    def parse_html(cls, raw_html: str, url: str) -> ScrapedPage:
        # 1. Extract title
        title = ""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = html.unescape(title_match.group(1).strip())

        # 2. Extract outbound links
        links: List[str] = []
        for m in re.finditer(r'<a\s+(?:[^>]*?\s+)?href=["\'](https?://[^"\']+)["\']', raw_html, re.IGNORECASE):
            link_url = m.group(1).strip()
            if link_url not in links:
                links.append(link_url)

        # 3. Strip boilerplate tags
        cleaned = raw_html
        for pattern in cls.BOILERPLATE_TAGS:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # If title not found in <title>, check <h1>
        if not title:
            h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", cleaned, re.IGNORECASE | re.DOTALL)
            if h1_match:
                title = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip()

        if not title:
            title = urlparse(url).netloc or "Web Page"

        # 4. Convert structural tags to markdown
        # Headings
        for level in range(1, 7):
            prefix = "#" * level
            cleaned = re.sub(
                rf"<h{level}[^>]*>(.*?)</h{level}>",
                rf"\n\n{prefix} \1\n\n",
                cleaned,
                flags=re.IGNORECASE | re.DOTALL,
            )

        # Paragraphs & divs
        cleaned = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\n\1\n\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)

        # List items
        cleaned = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Code blocks & inline code
        cleaned = re.sub(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", r"\n\n```\n\1\n```\n\n", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Strip head tag completely (title already extracted)
        cleaned = re.sub(r"<head\b[^<]*(?:(?!<\/head>)<[^<]*)*<\/head>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Bold & Italics
        cleaned = re.sub(r"<(?:strong|b)\b[^>]*>(.*?)</(?:strong|b)>", r"**\1**", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<(?:em|i)\b[^>]*>(.*?)</(?:em|i)>", r"*\1*", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Strip remaining HTML tags
        markdown = re.sub(r"<[^>]+>", "", cleaned)
        markdown = html.unescape(markdown)

        # Normalize whitespace and excessive newlines
        lines = [line.strip() for line in markdown.splitlines()]
        filtered_lines = []
        for line in lines:
            if line:
                filtered_lines.append(line)
            elif filtered_lines and filtered_lines[-1] != "":
                filtered_lines.append("")

        final_markdown = "\n".join(filtered_lines).strip()
        clean_text = re.sub(r"\s+", " ", re.sub(r"[#*`\-]", " ", final_markdown)).strip()

        sha256 = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

        return ScrapedPage(
            url=url,
            title=title,
            markdown_content=final_markdown,
            clean_text=clean_text,
            content_sha256=sha256,
            links=links[:50],
            retrieved_at=utc_now(),
        )
