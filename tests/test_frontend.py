"""
Playwright frontend tests.

These tests require a live Django server and a browser.
Run with: pytest tests/test_frontend.py --headed (or headless by default)

Requires: pip install pytest-playwright && playwright install
"""

import pytest

try:
    from playwright.sync_api import expect

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

pytestmark = [
    pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed"),
    pytest.mark.django_db(transaction=True),
]


@pytest.fixture
def create_items(db):
    from core.models import Item

    items = []
    for i in range(3):
        items.append(
            Item.objects.create(
                source="test",
                external_id=f"pw-{i}",
                title=f"Playwright Story {i}",
                url=f"https://example.com/{i}",
            )
        )
    return items


@pytest.fixture
def live_url(live_server):
    return live_server.url


class TestFrontend:
    def test_page_loads_and_displays_top_card(self, page, live_url, create_items):
        page.goto(live_url)
        card = page.locator(".card").first
        expect(card).to_be_visible()
        expect(card).to_contain_text("Playwright Story")

    def test_left_swipe_removes_card(self, page, live_url, create_items):
        page.goto(live_url)
        card = page.locator(".card").first
        title = card.inner_text()

        box = card.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx - 200, cy, steps=10)
        page.mouse.up()

        page.wait_for_timeout(500)
        expect(page.locator(".card").first).not_to_contain_text(title)

    def test_right_swipe_removes_card(self, page, live_url, create_items):
        page.goto(live_url)
        card = page.locator(".card").first
        title = card.inner_text()

        box = card.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx + 200, cy, steps=10)
        page.mouse.up()

        page.wait_for_timeout(500)
        expect(page.locator(".card").first).not_to_contain_text(title)

    def test_first_card_intercepts_pointer_events(self, page, live_url, create_items):
        page.goto(live_url)
        first_card = page.locator(".card").first
        box = first_card.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        is_first_card_or_child = page.evaluate(
            f"document.querySelector('.stack-container .card:first-child')"
            f".contains(document.elementFromPoint({cx}, {cy}))"
        )
        assert is_first_card_or_child, "Top card is covered by a later card; add z-index ordering"

    def test_empty_state_when_no_items(self, page, live_url, db):
        page.goto(live_url)
        expect(page.locator("#empty-state")).to_be_visible()
        expect(page.locator("#empty-state")).to_contain_text("all caught up")

    def test_radial_menu_appears_on_long_press(self, page, live_url, create_items):
        page.goto(live_url)
        card = page.locator(".card").first
        box = card.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        page.mouse.move(cx, cy)
        page.mouse.down()
        page.wait_for_timeout(600)

        expect(page.locator("#radial-menu")).to_be_visible()
        page.mouse.up()

    def test_radial_dismiss_removes_card(self, page, live_url, create_items):
        page.goto(live_url)
        card = page.locator(".card").first
        title = card.inner_text()
        box = card.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        page.mouse.move(cx, cy)
        page.mouse.down()
        page.wait_for_timeout(600)
        page.mouse.move(cx - 100, cy)
        page.mouse.up()

        page.wait_for_timeout(500)
        expect(page.locator(".card").first).not_to_contain_text(title)
