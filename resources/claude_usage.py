"""One card a day with how much of Sam's Claude subscription is left.

Briefer never calls Anthropic itself. It reads the snapshots that the Pi's
datalake-claude.timer writes every 10 minutes to
/var/lib/claude-usage/limits/*.parquet (from claude.ai's usage endpoint, so
they cover the whole account). Snapshots stop while the Claude Code login on
the Pi is expired, so the card says when its numbers are from.
"""
import logging
import os
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.models import Item
from resources.base import BaseResource

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Europe/London")
UTC = dt_timezone.utc
DEFAULT_LIMITS_DIR = "/var/lib/claude-usage/limits"
DEFAULT_DASHBOARD_URL = "https://pi.buttshee.net/dash/dashboards/tjgn8x891ykrk15giaaqhr5y"
WEEK = timedelta(days=7)

QUERY = """
    select fetched_at_utc, five_hour_pct, five_hour_resets_at_utc,
           seven_day_pct, seven_day_resets_at_utc
    from read_parquet(?, union_by_name = true)
    where seven_day_pct is not null
    order by fetched_at_utc
"""


def _utc(value):
    return value.replace(tzinfo=UTC) if value is not None else None


def _minute(value):
    """Reset times come back a few ms either side of the minute (14:59:59.98)."""
    if value is None:
        return None
    return (value + timedelta(seconds=30)).replace(second=0, microsecond=0)


def _round(value) -> int:
    """Round half up, as the weather card does."""
    return int(value + 0.5)


def _local(value: datetime) -> datetime:
    return value.astimezone(TIMEZONE)


def _when(value: datetime, now: datetime) -> str:
    """'06:17' today, 'Fri 23:40' within the week, else 'Thu 3 Dec 15:00'."""
    local, today = _local(value), _local(now).date()
    if local.date() == today:
        return f"{local:%H:%M}"
    if abs((local.date() - today).days) < 6 and value < now:
        return f"{local:%a %H:%M}"
    return f"{local:%a} {local.day} {local:%b %H:%M}"


def load_snapshots(limits_dir: str):
    files = sorted(Path(limits_dir).glob("*.parquet"))
    if not files:
        return []
    with duckdb.connect() as con:
        rows = con.execute(QUERY, [[str(f) for f in files]]).fetchall()
    return [
        {
            "fetched_at": _utc(r[0]),
            "five_hour_pct": r[1],
            "five_hour_resets_at": _minute(_utc(r[2])),
            "seven_day_pct": r[3],
            "seven_day_resets_at": _minute(_utc(r[4])),
        }
        for r in rows
    ]


def _hourly(points):
    """Keep the last point of each hour (one snapshot per 10 minutes is too many)."""
    by_hour = {}
    for ts, left in points:
        by_hour[ts.replace(minute=0, second=0, microsecond=0)] = (ts, left)
    return [[ts.isoformat(), left] for ts, left in by_hour.values()]


class ClaudeUsageResource(BaseResource):
    source_id = "claude-usage"

    def __init__(self, limits_dir=None, dashboard_url=None, now=None):
        self.limits_dir = limits_dir or os.environ.get("BRIEFER_CLAUDE_USAGE_DIR", DEFAULT_LIMITS_DIR)
        self.dashboard_url = dashboard_url or os.environ.get(
            "BRIEFER_CLAUDE_DASHBOARD_URL", DEFAULT_DASHBOARD_URL)
        self.now = now or timezone.now

    def fetch(self) -> None:
        now = self.now()
        today = _local(now).date()
        external_id = f"claude-usage-{today.isoformat()}"
        if Item.objects.filter(external_id=external_id).exists():
            logger.debug("Skipping already-fetched Claude usage: %s", external_id)
            return

        if not Path(self.limits_dir).is_dir():
            logger.warning("No Claude usage data: %s does not exist", self.limits_dir)
            return
        snapshots = load_snapshots(self.limits_dir)
        if not snapshots:
            logger.warning("No Claude usage snapshots in %s", self.limits_dir)
            return

        latest = snapshots[-1]
        as_of = latest["fetched_at"]
        week_reset = latest["seven_day_resets_at"]
        week_start = week_reset - WEEK if week_reset else None

        if week_reset and week_reset <= now:
            week_left = 100.0
            title = "Claude: weekly limit has reset, 100% left"
            summary = (f"reset {_when(week_reset, now + WEEK)}, "
                       f"after the last reading ({_when(as_of, now)})")
            points = []
        else:
            week_left = 100.0 - latest["seven_day_pct"]
            title = f"Claude: {_round(week_left)}% of weekly limit left"
            parts = []
            if week_reset:
                parts.append(f"resets {_when(week_reset, now)}")
            five_pct, five_reset = latest["five_hour_pct"], latest["five_hour_resets_at"]
            if five_pct is not None:
                if five_reset and five_reset <= now:
                    parts.append("5-hour session: 100% left")
                else:
                    five = f"5-hour session: {_round(100.0 - five_pct)}% left"
                    if five_reset:
                        five += f" until {_when(five_reset, now)}"
                    parts.append(five)
            parts.append(f"as of {_when(as_of, now)}")
            summary = " · ".join(parts)
            points = _hourly(
                (s["fetched_at"], 100.0 - s["seven_day_pct"])
                for s in snapshots
                if week_start is None or s["fetched_at"] >= week_start
            )

        end_of_day = datetime.combine(today + timedelta(days=1), time(), tzinfo=TIMEZONE)
        Item.objects.create(
            external_id=external_id,
            source=self.source_id,
            title=title,
            summary=summary,
            url=self.dashboard_url,
            metadata={
                "date": today.isoformat(),
                "as_of": as_of.isoformat(),
                "week_left_pct": week_left,
                "week_start": week_start.isoformat() if week_start else None,
                "week_resets_at": week_reset.isoformat() if week_reset else None,
                "five_hour_pct": latest["five_hour_pct"],
                "five_hour_resets_at": (latest["five_hour_resets_at"].isoformat()
                                        if latest["five_hour_resets_at"] else None),
                "points": points,
            },
            expires_at=end_of_day,
        )
        logger.info("Fetched Claude usage: %s", external_id)


# Chart: % of the weekly limit left across the current week, with a dashed
# line for an even pace (100% at the start, 0% at the reset).
W, H = 320, 92
TOP, BOTTOM = 6, 70  # plot area, y of 100% and 0%
LINE = "#2fa8bc"     # validated on the card surface (#16213e)
SURFACE = "#16213e"
INK_MUTED = "#8a8fa3"
INK = "#e0e0e0"
GRID = "#2a3a5e"


def render_chart(metadata) -> str:
    points = (metadata or {}).get("points") or []
    start, end = (metadata or {}).get("week_start"), (metadata or {}).get("week_resets_at")
    if not points or not start or not end:
        return ""
    t0, t1 = datetime.fromisoformat(start), datetime.fromisoformat(end)
    span = (t1 - t0).total_seconds()

    def xy(ts, left):
        x = (datetime.fromisoformat(ts) - t0).total_seconds() / span * W
        y = BOTTOM - (max(0.0, min(100.0, left)) / 100) * (BOTTOM - TOP)
        return round(min(max(x, 0), W), 1), round(y, 1)

    coords = [xy(ts, left) for ts, left in points]
    line = " ".join(f"{x},{y}" for x, y in coords)
    ex, ey = coords[-1]
    left = points[-1][1]
    label = f"{_round(left)}% left"
    lx, anchor = (ex + 8, "start") if ex < W - 70 else (ex - 8, "end")
    ly = ey + 4  # level with the point, beside it

    days = []
    for i in range(8):
        tick = t0 + timedelta(days=i)
        x = round(i / 7 * W, 1)
        anchor_d = "start" if i == 0 else "end" if i == 7 else "middle"
        days.append(f'<line x1="{x}" y1="{BOTTOM}" x2="{x}" y2="{BOTTOM + 3}" stroke="{GRID}"/>'
                    f'<text x="{x}" y="{H - 6}" text-anchor="{anchor_d}">{_local(tick):%a}</text>')

    desc = escape(f"Weekly Claude limit left: {label}, resets {_local(t1):%a %H:%M}")
    svg = (
        f'<svg class="usage-chart" viewBox="0 0 {W} {H}" width="100%" role="img" '
        f'aria-label="{desc}" font-size="10" fill="{INK_MUTED}" '
        f'font-family="-apple-system, BlinkMacSystemFont, sans-serif">'
        f'<title>{desc}</title>'
        f'<line x1="0" y1="{BOTTOM}" x2="{W}" y2="{BOTTOM}" stroke="{GRID}"/>'
        f'<line x1="0" y1="{TOP}" x2="{W}" y2="{BOTTOM}" stroke="{INK_MUTED}" '
        f'stroke-width="1" stroke-dasharray="3 4" opacity="0.7"/>'
        + "".join(days) +
        f'<polyline points="{line}" fill="none" stroke="{LINE}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{ex}" cy="{ey}" r="4" fill="{LINE}" stroke="{SURFACE}" stroke-width="2"/>'
        f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" fill="{INK}" font-weight="600">{label}</text>'
        f'</svg>'
    )
    return mark_safe(svg)
