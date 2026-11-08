"""Shared data model (Python side). Mirror of types.ts — keep both in sync (CLAUDE.md section 7)."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

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


# --- layout of the picture a visitor saves (mirror of guideLayout.ts) -------------------------------------------
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Fraction = Annotated[float, Field(ge=0, le=1)]


class _Box(BaseModel):
    id: Annotated[str, StringConstraints(max_length=32)]
    x: Fraction
    y: Fraction
    w: Annotated[float, Field(gt=0, le=1)]
    h: Annotated[float, Field(gt=0, le=1)]


class PhotoItem(_Box):
    type: Literal["photo"]
    fit: Literal["cover", "contain"] = "cover"


class TextItem(_Box):
    type: Literal["text"]
    text: Annotated[str, StringConstraints(max_length=4000)] = ""
    vertical: bool = False
    fontSize: Annotated[float, Field(ge=8, le=400)] | None = None  # canvas px; None = fit the box
    color: Color = "#1d2430"
    background: Color | None = None
    bold: bool = False
    align: Literal["start", "center", "end"] = "start"


class RectItem(_Box):
    type: Literal["rect"]
    fill: Color | None = None
    stroke: Color | None = None
    strokeWidth: Annotated[float, Field(ge=0, le=100)] = 4
    radius: Annotated[float, Field(ge=0, le=1000)] = 0


class ImageItem(_Box):
    type: Literal["image"]
    src: Annotated[str, StringConstraints(max_length=300_000, pattern=r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")]
    fit: Literal["cover", "contain"] = "contain"


GuideItem = Annotated[PhotoItem | TextItem | RectItem | ImageItem, Field(discriminator="type")]


class GuideLayout(BaseModel):
    """Arrangement of the saved picture on a fixed canvas (2048x1536 landscape or 1536x2048 portrait). Boxes are fractions of the canvas."""
    version: Literal[1] = 1
    orientation: Literal["landscape", "portrait"] = "landscape"
    background: Color = "#ffffff"
    items: Annotated[list[GuideItem], Field(max_length=30)] = []


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
    guideLayout: GuideLayout | None = None  # arrangement of the saved picture for a landscape photo; None = default
    guideLayoutPortrait: GuideLayout | None = None  # the same for a portrait photo
    guideText: str = ""  # explanation shown to the visitor with the photo they save; written by an administrator
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
