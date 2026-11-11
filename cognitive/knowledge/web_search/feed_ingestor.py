"""RSS & Atom Feed Ingestor (L3 Feature 3.07).

Parses RSS 2.0 and Atom feeds, tracks per-subscription refresh intervals and
seen item GUIDs so periodic polling surfaces only newly published updates.
"""

from __future__ import annotations

import hashlib
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

import httpx


@dataclass
class FeedItem:
    """Normalized article or regulatory entry parsed from RSS or Atom."""

    item_id: str
    title: str
    link: str
    summary: str
    published: str = ""
    feed_url: str = ""


@dataclass
class FeedSubscription:
    """Subscription state for periodic RSS/Atom polling."""

    feed_url: str
    refresh_interval_s: float = 3600.0
    last_checked_at: float = 0.0
    seen_ids: Set[str] = field(default_factory=set)
    category: str = "general"


class FeedIngestor:
    """Parses RSS 2.0 and Atom feeds and manages incremental periodic refreshes."""

    def __init__(self, fetcher: Optional[Callable[[str], str]] = None) -> None:
        self._fetcher = fetcher
        self._subscriptions: Dict[str, FeedSubscription] = {}

    @staticmethod
    def _tag_local(tag: str) -> str:
        return tag.split("}", 1)[-1].lower()

    @classmethod
    def parse_feed(cls, xml_content: str, feed_url: str = "") -> List[FeedItem]:
        """Parse RSS 2.0 or Atom XML string into normalized FeedItem entries."""
        root = ET.fromstring(xml_content)
        root_name = cls._tag_local(root.tag)
        items: List[FeedItem] = []

        if root_name == "rss" or root.find("channel") is not None:
            found_chan = root.find("channel")
            channel = found_chan if found_chan is not None else root
            for node in channel.findall("item"):
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                summary = (node.findtext("description") or "").strip()
                pub = (node.findtext("pubDate") or "").strip()
                guid = (node.findtext("guid") or link or hashlib.sha1(f"{title}:{pub}".encode()).hexdigest()).strip()
                items.append(
                    FeedItem(
                        item_id=guid,
                        title=title,
                        link=link,
                        summary=summary,
                        published=pub,
                        feed_url=feed_url,
                    )
                )
        else:
            # Atom feed handling with optional XML namespace
            for entry in root:
                if cls._tag_local(entry.tag) != "entry":
                    continue
                vals: Dict[str, str] = {}
                link_href = ""
                for child in entry:
                    lname = cls._tag_local(child.tag)
                    if lname == "link":
                        link_href = child.attrib.get("href") or (child.text or "").strip()
                    else:
                        vals[lname] = (child.text or "").strip()
                title = vals.get("title", "")
                pub = vals.get("updated") or vals.get("published", "")
                eid = vals.get("id") or link_href or hashlib.sha1(f"{title}:{pub}".encode()).hexdigest()
                items.append(
                    FeedItem(
                        item_id=eid,
                        title=title,
                        link=link_href,
                        summary=vals.get("summary") or vals.get("content", ""),
                        published=pub,
                        feed_url=feed_url,
                    )
                )
        return items

    def subscribe(
        self,
        feed_url: str,
        refresh_interval_s: float = 3600.0,
        category: str = "general",
    ) -> FeedSubscription:
        sub = FeedSubscription(feed_url=feed_url, refresh_interval_s=refresh_interval_s, category=category)
        self._subscriptions[feed_url] = sub
        return sub

    def is_due(self, feed_url: str, now: Optional[float] = None) -> bool:
        sub = self._subscriptions[feed_url]
        ref = now if now is not None else time.time()
        return (ref - sub.last_checked_at) >= sub.refresh_interval_s

    def ingest_xml(self, feed_url: str, xml_content: str, now: Optional[float] = None) -> List[FeedItem]:
        """Parse feed XML and return only unseen items since last check."""
        sub = self._subscriptions.get(feed_url) or self.subscribe(feed_url)
        parsed = self.parse_feed(xml_content, feed_url=feed_url)
        new_items: List[FeedItem] = []
        for item in parsed:
            if item.item_id not in sub.seen_ids:
                sub.seen_ids.add(item.item_id)
                new_items.append(item)
        sub.last_checked_at = now if now is not None else time.time()
        return new_items

    def refresh(self, feed_url: str, now: Optional[float] = None) -> List[FeedItem]:
        """Fetch feed XML (via configured fetcher or httpx) and return new items."""
        if self._fetcher is not None:
            xml_text = self._fetcher(feed_url)
        else:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(feed_url)
                resp.raise_for_status()
                xml_text = resp.text
        return self.ingest_xml(feed_url, xml_text, now=now)
