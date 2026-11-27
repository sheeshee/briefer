from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from django.template.loader import render_to_string

from core.models import Item
from resources.weather import WeatherResource, describe_weather_code


def _make_api_response(daily):
    response = MagicMock()
    response.json.return_value = {"daily": daily}
    response.raise_for_status.return_value = None
    return response


SAMPLE_DAILY = {
    "time": ["2026-11-27"],
    "weather_code": [61],
    "temperature_2m_max": [9.5],
    "temperature_2m_min": [4.4],
    "precipitation_probability_max": [100],
    "precipitation_sum": [12.2],
    "wind_speed_10m_max": [13.3],
    "sunrise": ["2026-11-27T07:50"],
    "sunset": ["2026-11-27T16:10"],
}


@pytest.mark.django_db
class TestWeatherResource:
    @patch("resources.weather.requests.get")
    def test_creates_one_card_for_today(self, mock_get):
        mock_get.return_value = _make_api_response(SAMPLE_DAILY)

        WeatherResource(latitude=51.49, longitude=-3.16, place="Cardiff").fetch()

        assert Item.objects.count() == 1
        item = Item.objects.get(external_id="weather-2026-11-27")
        assert item.source == "weather"
        assert item.title == "Cardiff: Slight rain, 4–10 °C"
        assert "100% chance of rain (12.2 mm)" in item.summary
        assert "wind up to 13 km/h" in item.summary
        assert "sunrise 07:50, sunset 16:10" in item.summary
        assert item.metadata["temp_max_c"] == 9.5
        assert item.metadata["weather_code"] == 61

    @patch("resources.weather.requests.get")
    def test_asks_for_the_configured_location(self, mock_get):
        mock_get.return_value = _make_api_response(SAMPLE_DAILY)

        WeatherResource(latitude=51.49, longitude=-3.16, place="Cardiff").fetch()

        params = mock_get.call_args.kwargs["params"]
        assert params["latitude"] == 51.49
        assert params["longitude"] == -3.16
        assert params["timezone"] == "Europe/London"
        assert params["forecast_days"] == 1

    @patch("resources.weather.requests.get")
    def test_idempotent_one_card_per_day(self, mock_get):
        mock_get.return_value = _make_api_response(SAMPLE_DAILY)

        resource = WeatherResource()
        resource.fetch()
        resource.fetch()

        assert Item.objects.count() == 1

    @patch("resources.weather.requests.get")
    def test_dry_day_says_no_rain(self, mock_get):
        daily = dict(SAMPLE_DAILY, weather_code=[1], precipitation_probability_max=[5],
                     precipitation_sum=[0.0])
        mock_get.return_value = _make_api_response(daily)

        WeatherResource(place="Cardiff").fetch()

        item = Item.objects.get()
        assert item.title.startswith("Cardiff: Mainly clear")
        assert "5% chance of rain" in item.summary
        assert "mm" not in item.summary

    @patch("resources.weather.requests.get")
    def test_expires_at_end_of_the_local_day(self, mock_get):
        mock_get.return_value = _make_api_response(SAMPLE_DAILY)

        WeatherResource().fetch()

        item = Item.objects.get()
        assert item.expires_at == datetime(2026, 11, 28, tzinfo=ZoneInfo("Europe/London"))

    def test_unknown_weather_code(self):
        assert describe_weather_code(999) == "Unknown"

    @patch("resources.weather.requests.get")
    def test_card_shows_the_summary(self, mock_get):
        mock_get.return_value = _make_api_response(SAMPLE_DAILY)
        WeatherResource().fetch()

        html = render_to_string("core/card.html", {"item": Item.objects.get()})

        assert "sunrise 07:50, sunset 16:10" in html
