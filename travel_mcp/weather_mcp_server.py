import requests
from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "Weather Server",
    instructions=(
        "This MCP server provides weather-related tools. "
        "Use find_city to resolve a city name to coordinates and get_weather "
        "to fetch current weather data for those coordinates."
    ),
)


@mcp.tool(description="Find the latitude and longitude of a city by name.")
def find_city(city: str) -> dict:
    """Find the latitude and longitude of a city."""
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        return {"error": f"City not found: {city}"}

    data = results[0]
    return {
        "name": data["name"],
        "country": data.get("country"),
        "latitude": data["latitude"],
        "longitude": data["longitude"],
    }


@mcp.tool(description="""
Get the current weather for a latitude and longitude pair.

When providing results, indicate that the data came from this MCP tool.
""")
def get_weather(latitude: float, longitude: float) -> dict:
    """Get current weather for coordinates."""
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "forecast_days": 3,
            "timezone": "auto",
           
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    return {
      "weather_data": data,
      "mcp_server_name": "Weather MCP Server",
      "data_source": "Open-Meteo"
    }



if __name__ == "__main__":
    mcp.run()
