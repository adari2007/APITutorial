"""Client for the external Open-Meteo weather service.

Open-Meteo is free and requires no API key. We use two of its endpoints:
  1. Geocoding  -> turn a location name into latitude/longitude.
  2. Forecast   -> fetch current weather for those coordinates.
"""
from __future__ import annotations

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Map Open-Meteo WMO weather codes to human-readable descriptions.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherServiceError(Exception):
    """Raised when the upstream weather service fails or returns no data."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LocationNotFoundError(WeatherServiceError):
    """Raised when the given location name cannot be geocoded."""

    def __init__(self, location: str):
        super().__init__(f"Location not found: {location!r}", status_code=404)


async def _geocode(client: httpx.AsyncClient, location: str) -> dict:
    """Resolve a location name to its coordinates via the geocoding endpoint."""
    resp = await client.get(
        GEOCODING_URL,
        params={"name": location, "count": 1, "language": "en", "format": "json"},
    )
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        raise LocationNotFoundError(location)
    return results[0]


async def _forecast(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    """Fetch the current weather for the given coordinates."""
    resp = await client.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "wind_speed_10m,weather_code",
            "timezone": "auto",
        },
    )
    resp.raise_for_status()
    return resp.json()


async def _daily_forecast(
    client: httpx.AsyncClient, lat: float, lon: float, days: int
) -> dict:
    """Fetch a multi-day daily forecast for the given coordinates."""
    resp = await client.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
            "apparent_temperature_max,apparent_temperature_min,"
            "precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
            "forecast_days": days,
            "timezone": "auto",
        },
    )
    resp.raise_for_status()
    return resp.json()


def _place_summary(place: dict, timezone: str | None) -> dict:
    """Build the normalized location block shared by both endpoints."""
    return {
        "name": place.get("name"),
        "country": place.get("country"),
        "admin1": place.get("admin1"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
        "timezone": timezone,
    }


async def get_weather(location: str) -> dict:
    """Look up `location` and return a normalized current-weather payload.

    Raises WeatherServiceError (or its subclasses) on failure.
    """
    timeout = httpx.Timeout(10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            place = await _geocode(client, location)
            forecast = await _forecast(client, place["latitude"], place["longitude"])
    except httpx.HTTPStatusError as exc:
        raise WeatherServiceError(
            f"Upstream weather service returned {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise WeatherServiceError(
            f"Could not reach upstream weather service: {exc}"
        ) from exc

    current = forecast.get("current", {})
    code = current.get("weather_code")

    return {
        "location": _place_summary(place, forecast.get("timezone")),
        "current": {
            "time": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "relative_humidity_pct": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": code,
            "description": WEATHER_CODES.get(code, "Unknown"),
        },
        "units": {
            "temperature": "°C",
            "wind_speed": "km/h",
            "humidity": "%",
        },
    }


async def get_forecast(location: str, days: int = 7) -> dict:
    """Look up `location` and return a normalized multi-day forecast.

    `days` is the number of forecast days (1-16, per Open-Meteo limits).
    Raises WeatherServiceError (or its subclasses) on failure.
    """
    timeout = httpx.Timeout(10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            place = await _geocode(client, location)
            forecast = await _daily_forecast(
                client, place["latitude"], place["longitude"], days
            )
    except httpx.HTTPStatusError as exc:
        raise WeatherServiceError(
            f"Upstream weather service returned {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise WeatherServiceError(
            f"Could not reach upstream weather service: {exc}"
        ) from exc

    daily = forecast.get("daily", {})
    dates = daily.get("time", [])

    # Open-Meteo returns each variable as a parallel list; zip them into
    # one object per day.
    days_out = []
    for i, date in enumerate(dates):
        code = _at(daily.get("weather_code"), i)
        days_out.append(
            {
                "date": date,
                "temperature_max_c": _at(daily.get("temperature_2m_max"), i),
                "temperature_min_c": _at(daily.get("temperature_2m_min"), i),
                "apparent_temperature_max_c": _at(
                    daily.get("apparent_temperature_max"), i
                ),
                "apparent_temperature_min_c": _at(
                    daily.get("apparent_temperature_min"), i
                ),
                "precipitation_sum_mm": _at(daily.get("precipitation_sum"), i),
                "precipitation_probability_max_pct": _at(
                    daily.get("precipitation_probability_max"), i
                ),
                "wind_speed_max_kmh": _at(daily.get("wind_speed_10m_max"), i),
                "weather_code": code,
                "description": WEATHER_CODES.get(code, "Unknown"),
            }
        )

    return {
        "location": _place_summary(place, forecast.get("timezone")),
        "forecast_days": len(days_out),
        "daily": days_out,
        "units": {
            "temperature": "°C",
            "wind_speed": "km/h",
            "precipitation": "mm",
            "precipitation_probability": "%",
        },
    }


def _at(values: list | None, index: int):
    """Safely read `values[index]`, returning None if unavailable."""
    if values is None or index >= len(values):
        return None
    return values[index]
