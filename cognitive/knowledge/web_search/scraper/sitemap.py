"""XML Sitemap Discovery & Traversal (L3 Feature 3.02)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SitemapEntry:
    loc: str
    lastmod: Optional[str] = None
    priority: float = 0.5


class SitemapParser:
    """Parses `<urlset>` and `<sitemapindex>` XML documents for web crawling."""

    @staticmethod
    def _local(tag: str) -> str:
        return tag.split("}", 1)[-1].lower()

    @classmethod
    def parse_xml(cls, xml_text: str, min_priority: float = 0.0) -> tuple[List[SitemapEntry], List[str]]:
        """Return `(url_entries, nested_sitemap_urls)` filtered by `min_priority`."""
        root = ET.fromstring(xml_text)
        root_name = cls._local(root.tag)
        entries: List[SitemapEntry] = []
        nested_sitemaps: List[str] = []

        if root_name == "sitemapindex":
            for child in root:
                if cls._local(child.tag) == "sitemap":
                    for sub in child:
                        if cls._local(sub.tag) == "loc" and sub.text:
                            nested_sitemaps.append(sub.text.strip())
            return entries, nested_sitemaps

        for child in root:
            if cls._local(child.tag) != "url":
                continue
            vals = {cls._local(sub.tag): (sub.text or "").strip() for sub in child}
            loc = vals.get("loc", "")
            if not loc:
                continue
            try:
                prio = float(vals["priority"]) if "priority" in vals and vals["priority"] else 0.5
            except ValueError:
                prio = 0.5
            if prio >= min_priority:
                entries.append(SitemapEntry(loc=loc, lastmod=vals.get("lastmod") or None, priority=prio))

        entries.sort(key=lambda e: e.priority, reverse=True)
        return entries, nested_sitemaps

