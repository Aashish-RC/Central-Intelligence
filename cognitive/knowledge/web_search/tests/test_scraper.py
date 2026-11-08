"""Unit tests for HTML-to-Markdown parsing and polite crawler."""

import pytest
from web_search.scraper.parser import HTMLMarkdownParser
from web_search.scraper.crawler import PoliteCrawler


def test_html_to_markdown_and_boilerplate_stripping():
    raw_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Galois/Counter Mode (GCM) Specification</title>
        <script>console.log("analytics tracking code");</script>
        <style>.ad-banner { display: block; }</style>
    </head>
    <body>
        <nav><a href="/home">Home</a> | <a href="/about">About</a></nav>
        <header><h1>Header Navigation</h1></header>
        <main>
            <h1>Galois/Counter Mode (GCM)</h1>
            <p>NIST SP 800-38D specifies Galois/Counter Mode (GCM) for authenticated encryption with AES-256.</p>
            <p>It provides both <strong>data confidentiality</strong> and <em>authenticity assurance</em>.</p>
            <ul>
                <li>Key size: 256 bits</li>
                <li>Tag length: 128 bits</li>
            </ul>
            <pre><code>cipher = AES.new(key, AES.MODE_GCM)</code></pre>
        </main>
        <aside><div class="ad">Buy our crypto book!</div></aside>
        <footer><p>Copyright 2026 NIST</p></footer>
    </body>
    </html>
    """

    page = HTMLMarkdownParser.parse_html(raw_html, url="https://csrc.nist.gov/sp800-38d")
    assert page.title == "Galois/Counter Mode (GCM) Specification"
    assert page.url == "https://csrc.nist.gov/sp800-38d"
    assert len(page.content_sha256) == 64

    # Ensure boilerplate tags were stripped
    assert "analytics tracking code" not in page.markdown_content
    assert "ad-banner" not in page.markdown_content
    assert "Header Navigation" not in page.markdown_content
    assert "Buy our crypto book!" not in page.markdown_content

    # Ensure content was converted to markdown
    assert "# Galois/Counter Mode (GCM)" in page.markdown_content
    assert "**data confidentiality**" in page.markdown_content
    assert "*authenticity assurance*" in page.markdown_content
    assert "- Key size: 256 bits" in page.markdown_content
    assert "cipher = AES.new(key, AES.MODE_GCM)" in page.markdown_content


def test_polite_crawler_with_override():
    crawler = PoliteCrawler()
    page = crawler.scrape(
        url="https://example.com/test",
        html_override="<html><head><title>Test Page</title></head><body><h1>Hello World</h1><p>Test body</p></body></html>",
    )
    assert page.title == "Test Page"
    assert "# Hello World" in page.markdown_content
    assert "Test body" in page.clean_text
