from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolContext, ToolError

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherInput(BaseModel):
    location: str = Field(description="City name, e.g. 'Paris' or 'Lyon, France'.")
    days: int = Field(default=3, ge=1, le=7, description="Number of forecast days (1-7).")


async def _weather(inp: WeatherInput, ctx: ToolContext) -> str:
    name = inp.location.split(",")[0].strip()
    geo = await ctx.cached_get_json(GEOCODE_URL, {"name": name, "count": 1})
    if not geo.get("results"):
        raise ToolError(f"Location not found: {inp.location}")
    place = geo["results"][0]
    data = await ctx.cached_get_json(
        FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "wind_speed_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "forecast_days": inp.days,
            "timezone": "auto",
        },
    )
    cur = data.get("current", {})
    daily = data.get("daily", {})
    lines = [
        f"{place['name']}, {place.get('country', '')} (lat {place['latitude']}, "
        f"lon {place['longitude']})",
        f"Now ({cur.get('time')}): {cur.get('temperature_2m')}°C, feels like "
        f"{cur.get('apparent_temperature')}°C, humidity {cur.get('relative_humidity_2m')}%, "
        f"wind {cur.get('wind_speed_10m')} km/h, WMO code {cur.get('weather_code')}",
    ]
    for i, day in enumerate(daily.get("time", [])):
        lines.append(
            f"{day}: min {daily['temperature_2m_min'][i]}°C / max "
            f"{daily['temperature_2m_max'][i]}°C, precip {daily['precipitation_sum'][i]} mm, "
            f"WMO code {daily['weather_code'][i]}"
        )
    return "\n".join(lines)


weather = Tool(
    name="get_weather",
    description="Current conditions and a daily forecast for a city (Open-Meteo, live data).",
    input_model=WeatherInput,
    handler=_weather,
)
