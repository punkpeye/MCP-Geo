from geopy.geocoders import Nominatim, ArcGIS, Bing
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import os
from geopy.extra.rate_limiter import RateLimiter
from fastmcp import FastMCP

'''how to use this code
uv pip install -r requirements.txt
add to mcp server config

{
    "mcp-geo": {
        "command": "uv",
        "args": [
        "run",
        "--with",
        "fastmcp",
        "fastmcp",
        "run",
        "MCP-Geo/geo.py"
        ],
        "env": {
        "NOMINATIM_URL": "${NOMINATIM_URL}",
        "SCHEME": "http",
        "GEOCODER_PROVIDER": "nominatim"
        }
    }
}

'''
# Instantiate FastMCP server
mcp = FastMCP("MCP Geo", dependencies=["geopy"])



# If you need HTTPS, ensure scheme='https' and domain=some-url.

# Decide which geocoder to use based on env var
geocoder_name = os.environ.get("GEOCODER_PROVIDER", "nominatim").lower()

if geocoder_name == "nominatim":
    # For Nominatim, read the domain from NOMINATIM_URL or default to openstreetmap
    domain = os.environ.get("NOMINATIM_URL", "nominatim.openstreetmap.org")
    scheme = os.environ.get("SCHEME", "http")
    # If you need https, set scheme='https'
    app = Nominatim(domain=domain, scheme=scheme)
elif geocoder_name == "arcgis":
    # ArcGIS typically just works; optionally pass username/password or referer
    # if needed for premium data.
    # Read additional env vars if you have them, e.g., ARC_USERNAME, ARC_PASSWORD
    # i dont use this but if desired, you can add the env vars to the mcp server config
    app = ArcGIS(user=os.environ.get("ARC_USERNAME", ""), password=os.environ.get("ARC_PASSWORD", ""))
elif geocoder_name == "bing":
    # For Bing, you typically need an API key
    bing_key = os.environ.get("BING_API_KEY", "")
    if not bing_key:
        raise ValueError("Missing BING_API_KEY env var for Bing geocoder.")
    app = Bing(api_key=bing_key)
else:
    raise ValueError(f"Unsupported geocoder provider: {geocoder_name}")


geocode = RateLimiter(app.geocode, min_delay_seconds=1)
reverse = RateLimiter(app.reverse, min_delay_seconds=1)





@mcp.tool()
def geocode_location(location_str: str) -> dict | None:
    """
    Geocodes a single location string (an address or place name).
    Returns {'latitude', 'longitude', 'address'} or None if not found.
    """
    try:
        location = geocode.geocode(location_str)
        if not location:
            return None
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "address": location.address
        }
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error: {e}")
        return None


@mcp.tool()
def reverse_geocode(lat: float, lon: float) -> dict | None:
    """
    Reverse geocodes a latitude and longitude to find the nearest address.
    Returns {'latitude', 'longitude', 'address'} or None if not found.
    """
    try:
        location = reverse.reverse((lat, lon))
        if not location:
            return None
        return {
            "latitude": lat,
            "longitude": lon,
            "address": location.address
        }
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Reverse geocoding error: {e}")
        return None


@mcp.tool()
def geocode_with_details(location_str: str) -> dict | None:
    """
    Geocodes a single location string with extra details such as bounding box
    and detailed address info, if available.
    """
    try:
        location = app.geocode(location_str, addressdetails=True)
        if not location:
            return None
        return {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "address": location.address,
            "details": location.raw.get("address", {}),
            "bounding_box": location.raw.get("boundingbox", [])
        }
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error: {e}")
        return None


@mcp.tool()
def geocode_multiple_locations(location_strs: list[str]) -> list[dict | None]:
    """
    Geocodes multiple address strings, returning a list of results.
    Each element is either:
      {
        "latitude": float,
        "longitude": float,
        "address": str
      }
    or None if no result was found.
    This function uses the same RateLimiter above, so it waits min_delay_seconds
    between each geocode call to respect usage limits.
    """
    results = []
    for loc_str in location_strs:
        try:
            location = geocode.geocode(loc_str)
            if not location:
                results.append(None)
            else:
                results.append({
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "address": location.address
                })
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Geocoding error for '{loc_str}': {e}")
            results.append(None)
    return results

@mcp.tool()
def reverse_geocode_multiple_locations(coords: list[list[float]]) -> list[dict | None]:
    """
    Reverse geocodes multiple [latitude, longitude] pairs to find the nearest address.

    Each item in `coords` should be a list with two floats: [lat, lon].
    Example: [[37.7749, -122.4194], [40.7128, -74.0060]]

    Returns a list of results, where each result is either:
        {
          "latitude": float,
          "longitude": float,
          "address": str
        }
    or None if the location could not be found or an error occurred.

    This function uses the same RateLimiter above, so it waits at least
    min_delay_seconds between each reverse geocode call.
    """
    results = []
    for latlon in coords:
        if len(latlon) != 2:
            # If there's a malformed input, skip it
            results.append(None)
            continue

        lat, lon = latlon
        try:
            location = reverse.reverse((lat, lon))
            if not location:
                results.append(None)
            else:
                results.append({
                    "latitude": lat,
                    "longitude": lon,
                    "address": location.address
                })
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Reverse geocoding error for ({lat}, {lon}): {e}")
            results.append(None)

    return results