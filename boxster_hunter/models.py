"""Pydantic v2 model for a normalized listing."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Listing(BaseModel):
    """A normalized listing from any source."""

    model_config = ConfigDict(extra="forbid")

    # Identity
    source: str
    source_id: str
    url: HttpUrl
    first_seen: datetime
    last_updated: datetime

    # Vehicle specs (parsed)
    year: int | None = None
    model: str | None = None
    trim: str | None = None
    transmission: str | None = None
    mileage: int | None = None
    color_exterior: str | None = None
    color_interior: str | None = None
    engine: str | None = None
    vin: str | None = None

    # Listing details
    price: int | None = None
    price_is_auction: bool = False
    auction_end: datetime | None = None
    location: str | None = None
    seller_type: str | None = None

    # Match quality (populated by scoring engine)
    score: int = 0
    tier: str = "UNSCORED"
    flags: list[str] = Field(default_factory=list)
    color_match: dict[str, Any] | None = None

    # IMS intelligence
    has_ims_solution: bool = False
    has_ims_retrofit: bool = False
    has_ims_replaced: bool = False

    # Raw content for review
    title: str
    description: str = ""
    image_urls: list[str] = Field(default_factory=list)

    @property
    def url_str(self) -> str:
        return str(self.url)
