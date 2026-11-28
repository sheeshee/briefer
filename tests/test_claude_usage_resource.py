from datetime import datetime, timedelta, timezone as dt_timezone

import duckdb
import pytest
from django.template import Context, Template

from core.models import Item
from resources.claude_usage import ClaudeUsageResource, render_chart

UTC = dt_timezone.utc
WEEK_RESET = datetime(2026, 12, 3, 15, 0, tzinfo=UTC)  # Thursday


def _write_snapshots(limits_dir, rows, name="2026-11-28.parquet"):
    """rows: (fetched_at, five_hour_pct, five_hour_reset, seven_day_pct, seven_day_reset)."""
    limits_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("""
        create table t (
            fetched_at_utc timestamp, five_hour_pct double, five_hour_resets_at_utc timestamp,
            seven_day_pct double, seven_day_resets_at_utc timestamp, raw varchar)
    """)
    naive = lambda d: d.astimezone(UTC).replace(tzinfo=None) if d else None
    for fetched, five, five_reset, week, week_reset in rows:
        con.execute("insert into t values (?, ?, ?, ?, ?, '{}')",
                    [naive(fetched), five, naive(five_reset), week, naive(week_reset)])
    con.execute(f"copy t to '{limits_dir / name}' (format parquet)")


def _week_of_snapshots(limits_dir, until, last_week_pct=13.0, five=20.0, five_reset=None):
    start = WEEK_RESET - timedelta(days=7)
    rows = []
    t = start + timedelta(minutes=7)
    while t < until:
        frac = (t - start) / (until - start)
        rows.append((t, 0.0, None, round(last_week_pct * frac, 1), WEEK_RESET))
        t += timedelta(minutes=10)
    rows.append((until, five, five_reset, last_week_pct, WEEK_RESET))
    _write_snapshots(limits_dir, rows)
    return rows


@pytest.fixture
def limits_dir(tmp_path):
    return tmp_path / "limits"


def _resource(limits_dir, now):
    return ClaudeUsageResource(limits_dir=str(limits_dir),
                               dashboard_url="https://pi.example/dash/dashboards/abc",
                               now=lambda: now)


@pytest.mark.django_db
class TestClaudeUsageResource:
    def test_creates_one_card_with_weekly_left(self, limits_dir):
        now = datetime(2026, 11, 28, 6, 30, tzinfo=UTC)
        _week_of_snapshots(limits_dir, until=datetime(2026, 11, 28, 6, 17, tzinfo=UTC),
                           five=20.0, five_reset=datetime(2026, 11, 28, 9, 0, tzinfo=UTC))

        _resource(limits_dir, now).fetch()

        item = Item.objects.get()
        assert item.external_id == "claude-usage-2026-11-28"
        assert item.source == "claude-usage"
        assert item.title == "Claude: 87% of weekly limit left"
        assert "resets Thu 3 Dec 15:00" in item.summary
        assert "5-hour session: 80% left until 09:00" in item.summary
        assert "as of 06:17" in item.summary
        assert item.url == "https://pi.example/dash/dashboards/abc"
        assert item.metadata["week_left_pct"] == 87.0
        assert item.metadata["week_resets_at"] == "2026-12-03T15:00:00+00:00"

    def test_expires_at_local_midnight(self, limits_dir):
        now = datetime(2026, 11, 28, 6, 30, tzinfo=UTC)
        _week_of_snapshots(limits_dir, until=datetime(2026, 11, 28, 6, 17, tzinfo=UTC))

        _resource(limits_dir, now).fetch()

        assert Item.objects.get().expires_at == datetime(2026, 11, 29, 0, 0, tzinfo=UTC)

    def test_idempotent_one_card_per_day(self, limits_dir):
        now = datetime(2026, 11, 28, 6, 30, tzinfo=UTC)
        _week_of_snapshots(limits_dir, until=datetime(2026, 11, 28, 6, 17, tzinfo=UTC))

        resource = _resource(limits_dir, now)
        resource.fetch()
        resource.fetch()

        assert Item.objects.count() == 1

    def test_points_cover_this_week_hourly(self, limits_dir):
        now = datetime(2026, 11, 28, 6, 30, tzinfo=UTC)
        _week_of_snapshots(limits_dir, until=datetime(2026, 11, 28, 6, 17, tzinfo=UTC))
        # A snapshot from the previous week must not be in the chart.
        _write_snapshots(limits_dir, [(datetime(2026, 11, 25, 12, 0, tzinfo=UTC), 0.0, None, 90.0,
                                       datetime(2026, 11, 26, 15, 0, tzinfo=UTC))], name="old.parquet")

        _resource(limits_dir, now).fetch()

        meta = Item.objects.get().metadata
        assert meta["week_start"] == "2026-11-26T15:00:00+00:00"
        points = meta["points"]
        assert all(left >= 87.0 for _, left in points)
        assert points[-1] == ["2026-11-28T06:17:00+00:00", 87.0]
        hours = [p[0][:13] for p in points]
        assert len(hours) == len(set(hours))

    def test_old_snapshot_shows_day_and_time(self, limits_dir):
        now = datetime(2026, 11, 28, 6, 30, tzinfo=UTC)
        _week_of_snapshots(limits_dir, until=datetime(2026, 11, 27, 23, 40, tzinfo=UTC))

        _resource(limits_dir, now).fetch()

        assert "as of Fri 23:40" in Item.objects.get().summary

    def test_five_hour_window_over_since_snapshot_is_full(self, limits_dir):
        now = datetime(2026, 11, 28, 6, 30, tzinfo=UTC)
        _week_of_snapshots(limits_dir, until=datetime(2026, 11, 27, 23, 40, tzinfo=UTC),
                           five=60.0, five_reset=datetime(2026, 11, 28, 2, 0, tzinfo=UTC))

        _resource(limits_dir, now).fetch()

        assert "5-hour session: 100% left" in Item.objects.get().summary

    def test_weekly_reset_since_last_snapshot(self, limits_dir):
        now = datetime(2026, 12, 3, 16, 0, tzinfo=UTC)
        _week_of_snapshots(limits_dir, until=datetime(2026, 12, 3, 9, 0, tzinfo=UTC), last_week_pct=70.0)

        _resource(limits_dir, now).fetch()

        item = Item.objects.get()
        assert item.title == "Claude: weekly limit has reset, 100% left"
        assert "reset Thu 3 Dec 15:00, after the last reading (09:00)" in item.summary
        assert item.metadata["week_left_pct"] == 100.0

    def test_no_snapshots_makes_no_card(self, limits_dir):
        _write_snapshots(limits_dir, [], name="empty.parquet")

        _resource(limits_dir, datetime(2026, 11, 28, 6, 30, tzinfo=UTC)).fetch()

        assert Item.objects.count() == 0

    def test_missing_directory_makes_no_card(self, limits_dir):
        _resource(limits_dir, datetime(2026, 11, 28, 6, 30, tzinfo=UTC)).fetch()

        assert Item.objects.count() == 0

    def test_uk_summer_time_shown_in_local_time(self, limits_dir):
        reset = datetime(2026, 7, 2, 14, 0, tzinfo=UTC)
        snap = datetime(2026, 6, 27, 5, 17, tzinfo=UTC)
        _write_snapshots(limits_dir, [(snap, 0.0, None, 10.0, reset)])

        _resource(limits_dir, datetime(2026, 6, 27, 5, 30, tzinfo=UTC)).fetch()

        item = Item.objects.get()
        assert "resets Thu 2 Jul 15:00" in item.summary
        assert "as of 06:17" in item.summary


class TestRenderChart:
    META = {
        "week_start": "2026-11-26T15:00:00+00:00",
        "week_resets_at": "2026-12-03T15:00:00+00:00",
        "points": [["2026-11-26T15:07:00+00:00", 100.0], ["2026-11-28T06:17:00+00:00", 87.0]],
        "week_left_pct": 87.0,
    }

    def test_renders_svg_with_line_and_pace(self):
        svg = render_chart(self.META)
        assert svg.startswith("<svg")
        assert "polyline" in svg
        assert 'stroke-dasharray' in svg  # even-pace line
        assert "87% left" in svg

    def test_empty_without_points(self):
        assert render_chart({"points": []}) == ""
        assert render_chart({}) == ""

    def test_template_tag(self):
        out = Template("{% load claude_usage %}{% claude_usage_chart meta %}").render(
            Context({"meta": self.META}))
        assert out.startswith("<svg")


@pytest.mark.django_db
def test_card_shows_summary_chart_and_short_link():
    from django.template.loader import render_to_string
    item = Item.objects.create(
        source="claude-usage", external_id="claude-usage-2026-11-28",
        title="Claude: 87% of weekly limit left", summary="resets Thu 3 Dec 15:00 · as of 06:17",
        url="https://pi.example/dash/dashboards/abc", metadata=TestRenderChart.META)
    html = render_to_string("core/card.html", {"item": item})
    assert "resets Thu 3 Dec 15:00" in html
    assert "<svg" in html
    assert ">Shaper dashboard<" in html


@pytest.mark.django_db
def test_reset_time_rounded_to_nearest_minute(tmp_path):
    limits = tmp_path / "limits"
    jitter = datetime(2026, 12, 3, 14, 59, 59, 985000, tzinfo=UTC)
    _write_snapshots(limits, [(datetime(2026, 11, 28, 6, 27, tzinfo=UTC), 4.0,
                               datetime(2026, 11, 28, 11, 19, 59, 600000, tzinfo=UTC), 14.0, jitter)])

    _resource(limits, datetime(2026, 11, 28, 6, 30, tzinfo=UTC)).fetch()

    item = Item.objects.get()
    assert "resets Thu 3 Dec 15:00" in item.summary
    assert "until 11:20" in item.summary
    assert item.metadata["week_resets_at"] == "2026-12-03T15:00:00+00:00"
