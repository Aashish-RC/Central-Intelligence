"""Marketplace Catalog: Extension publishing, search, categorization, and bundle downloads."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid

from ..core.models import PackageBundle, PackageType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceCategory(str, Enum):
    CODING = "coding"
    DATA_ANALYSIS = "data_analysis"
    DEVOPS = "devops"
    UTILITIES = "utilities"
    COMMUNICATION = "communication"
    RESEARCH = "research"
    SECURITY = "security"


class MarketplaceItem(BaseModel):
    item_id: str
    name: str
    package_type: PackageType
    category: MarketplaceCategory
    version: str
    description: str
    author: str = "Pheonix Community"
    downloads: int = 0
    rating: float = 5.0
    required_tier: str = "free"  # free, pro, enterprise
    tags: List[str] = Field(default_factory=list)
    published_at: datetime = Field(default_factory=utc_now)


class MarketplaceCatalog:
    """Manages discoverable extensions, bundles, and metadata search."""

    def __init__(self):
        self._items: Dict[str, MarketplaceItem] = {}
        self._bundles: Dict[str, PackageBundle] = {}

    def publish_item(self, item: MarketplaceItem, bundle: Optional[PackageBundle] = None) -> None:
        self._items[item.item_id] = item
        if bundle:
            self._bundles[item.item_id] = bundle

    def get_item(self, item_id: str) -> Optional[MarketplaceItem]:
        return self._items.get(item_id)

    def get_bundle(self, item_id: str) -> Optional[PackageBundle]:
        item = self._items.get(item_id)
        if item:
            item.downloads += 1
        return self._bundles.get(item_id)

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[MarketplaceCategory] = None,
        max_tier: Optional[str] = None,
    ) -> List[MarketplaceItem]:
        results = list(self._items.values())

        if category:
            results = [i for i in results if i.category == category]

        tier_weights = {"free": 1, "pro": 2, "enterprise": 3}
        if max_tier and max_tier in tier_weights:
            allowed_max = tier_weights[max_tier]
            results = [i for i in results if tier_weights.get(i.required_tier, 1) <= allowed_max]

        if query:
            q_lower = query.lower()
            results = [
                i
                for i in results
                if q_lower in i.name.lower()
                or q_lower in i.description.lower()
                or any(q_lower in tag.lower() for tag in i.tags)
            ]

        # Sort by downloads descending
        results.sort(key=lambda x: x.downloads, reverse=True)
        return results
