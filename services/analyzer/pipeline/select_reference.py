"""Stage 7 (P1): pick the reference photo closest to the capture's season and time of day."""
from datetime import datetime, timedelta, timezone

from shared.adapters.ports import Stored
from shared.schemas.models import Reference

JST = timezone(timedelta(hours=9))
_SEASONS = ["winter", "winter", "spring", "spring", "spring", "summer",
            "summer", "summer", "autumn", "autumn", "autumn", "winter"]  # index = month - 1
_SEASON_ORDER = ["spring", "summer", "autumn", "winter"]


def season_of(dt: datetime) -> str:
    return _SEASONS[dt.astimezone(JST).month - 1]


def time_of_day_of(dt: datetime) -> str:
    h = dt.astimezone(JST).hour
    return "morning" if h < 10 else "day" if h < 16 else "evening"


def _season_distance(a: str, b: str) -> int:
    d = abs(_SEASON_ORDER.index(a) - _SEASON_ORDER.index(b))
    return min(d, 4 - d)


def select_reference(refs: list[Stored[Reference]], captured_at: datetime) -> Stored[Reference] | None:
    """Prefer the same time of day and the nearest season; references with no tags count as neutral."""
    if not refs:
        return None
    season, tod = season_of(captured_at), time_of_day_of(captured_at)

    def cost(r: Stored[Reference]) -> tuple[int, int, str]:
        s_cost = 1 if r.data.season is None else _season_distance(r.data.season, season) * 2
        t_cost = 1 if r.data.timeOfDay is None else (0 if r.data.timeOfDay == tod else 2)
        return (s_cost + t_cost, 0, r.id)

    return min(refs, key=cost)
