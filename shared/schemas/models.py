"""Shared data model (Python side). Mirror of types.ts — keep both in sync (CLAUDE.md section 7)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ok = no change / needs_review = waiting for a human / confirmed_change = a human confirmed a change
SpotStatus = Literal["ok", "needs_review", "confirmed_change"]
DetectionStatus = Literal["no_change", "needs_review", "confirmed_change", "false_positive", "monitoring"]
Season = Literal["spring", "summer", "autumn", "winter"]
TimeOfDay = Literal["morning", "day", "evening"]

# Statuses an admin may set when reviewing (CLAUDE.md section 3, screen 6).
REVIEW_DECISIONS: tuple[str, ...] = ("confirmed_change", "false_positive", "monitoring")


class LatLng(BaseModel):
    lat: float
    lng: float


class Box(BaseModel):
    """Pixel coordinates in the aligned reference photo."""
    x: int
    y: int
    width: int
    height: int


class Change(BaseModel):
    category: str                       # one of the template's observationItems
    box: Box
    confidence: float = Field(ge=0, le=1)
    reason: str


class Site(BaseModel):
    name: str
    address: str = ""
    adminUids: list[str] = []


class Group(BaseModel):
    """A structure (e.g. one stone wall, a keep) that several spots belong to. Added to the CLAUDE.md data design."""
    siteId: str
    name: str
    createdAt: datetime | None = None


class Spot(BaseModel):
    siteId: str
    name: str
    groupId: str | None = None
    location: LatLng
    standingNote: str = ""
    templateId: str
    status: SpotStatus = "ok"
    captureUrl: str = ""
    createdAt: datetime | None = None


class Reference(BaseModel):
    spotId: str
    storagePath: str
    season: Season | None = None
    timeOfDay: TimeOfDay | None = None
    active: bool = True


class Quality(BaseModel):
    passed: bool
    reasons: list[str] = []


class Photo(BaseModel):
    siteId: str                         # denormalized from the spot, so security rules can check access
    spotId: str
    storagePath: str                    # blurred image only
    capturedAt: datetime
    quality: Quality
    uploaderUid: str                    # anonymous uid


class Detection(BaseModel):
    siteId: str                         # denormalized from the spot, so security rules can check access
    photoId: str
    spotId: str
    referenceId: str
    changes: list[Change] = []
    maxConfidence: float = 0.0
    status: DetectionStatus = "no_change"
    reviewedBy: str | None = None
    reviewedAt: datetime | None = None
    model: str = ""
    createdAt: datetime | None = None


class Template(BaseModel):
    name: str
    observationItems: list[str]
    promptInstruction: str
