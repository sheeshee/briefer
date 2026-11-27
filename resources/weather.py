import logging
import math
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests

from core.models import Item
from resources.base import BaseResource

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Europe/London"

# Centre of the CF24 postcode district (Cardiff), not the house: the same
# point the datalake's weather dataset uses.
DEFAULT_LATITUDE = 51.49
DEFAULT_LONGITUDE = -3.16
DEFAULT_PLACE = "Cardiff"
DEFAULT_URL = "https://www.bbc.co.uk/weather/2653822"

DAILY_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "precipitation_sum",
    "wind_speed_10m_max",
    "sunrise",
    "sunset",
]

# WMO weather interpretation codes, as documented by Open-Meteo.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Slight rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Slight snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Violent showers",
    85: "Light snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code) -> str:
    return WEATHER_CODES.get(code, "Unknown")


def _round(value) -> int:
    """Round half up (Python's round() rounds 4.5 to 4)."""
    return math.floor(value + 0.5)


def _clock(iso_value: str) -> str:
    return iso_value.split("T", 1)[1][:5] if "T" in iso_value else iso_value


class WeatherResource(BaseResource):
    """One card a day with today's forecast from Open-Meteo (no API key)."""

    source_id = "weather"

    def __init__(self, latitude=None, longitude=None, place=None, url=None):
        self.latitude = latitude if latitude is not None else float(
            os.environ.get("BRIEFER_WEATHER_LATITUDE", DEFAULT_LATITUDE))
        self.longitude = longitude if longitude is not None else float(
            os.environ.get("BRIEFER_WEATHER_LONGITUDE", DEFAULT_LONGITUDE))
        self.place = place or os.environ.get("BRIEFER_WEATHER_PLACE", DEFAULT_PLACE)
        self.url = url or os.environ.get("BRIEFER_WEATHER_URL", DEFAULT_URL)

    def fetch(self) -> None:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": self.latitude,
                "longitude": self.longitude,
                "daily": ",".join(DAILY_FIELDS),
                "timezone": TIMEZONE,
                "forecast_days": 1,
            },
            timeout=30,
        )
        response.raise_for_status()
        daily = response.json()["daily"]
        day = {field: values[0] for field, values in daily.items()}

        external_id = f"weather-{day['time']}"
        if Item.objects.filter(external_id=external_id).exists():
            logger.debug("Skipping already-fetched forecast: %s", external_id)
            return

        condition = describe_weather_code(day["weather_code"])
        low = _round(day["temperature_2m_min"])
        high = _round(day["temperature_2m_max"])
        title = f"{self.place}: {condition}, {low}–{high} °C"

        rain = f"{day['precipitation_probability_max']}% chance of rain"
        if day["precipitation_sum"]:
            rain += f" ({day['precipitation_sum']:.1f} mm)"
        summary = " · ".join([
            rain,
            f"wind up to {_round(day['wind_speed_10m_max'])} km/h",
            f"sunrise {_clock(day['sunrise'])}, sunset {_clock(day['sunset'])}",
        ])

        tz = ZoneInfo(TIMEZONE)
        end_of_day = datetime.combine(
            date.fromisoformat(day["time"]) + timedelta(days=1), time(), tzinfo=tz)

        Item.objects.create(
            external_id=external_id,
            source=self.source_id,
            title=title,
            summary=summary,
            url=self.url,
            metadata={
                "date": day["time"],
                "place": self.place,
                "weather_code": day["weather_code"],
                "condition": condition,
                "temp_min_c": day["temperature_2m_min"],
                "temp_max_c": day["temperature_2m_max"],
                "precipitation_probability": day["precipitation_probability_max"],
                "precipitation_mm": day["precipitation_sum"],
                "wind_max_kmh": day["wind_speed_10m_max"],
                "sunrise": day["sunrise"],
                "sunset": day["sunset"],
            },
            expires_at=end_of_day,
        )
        logger.info("Fetched forecast: %s", external_id)
