#!/usr/bin/env python3
import sys, time, json
from pathlib import Path

REPO_ROOT = Path("/home/pskillman/pi/FlightTracker")
sys.path.insert(0, str(REPO_ROOT))

from FlightRadar24.api import FlightRadar24API

def main():
    fr = FlightRadar24API()

    # Use your exact bounds string
    bounds = "35.84,35.98,-78.78,-78.62"

    # The library stores request session / internals; we’ll reach into it carefully.
    # Many versions use: self._session (requests.Session) and self._get(...) helpers.
    api = fr

    # Try common internal attributes without assuming too much.
    sess = getattr(api, "_session", None) or getattr(api, "_FlightRadar24API__session", None)
    base = getattr(api, "BASE_URL", None) or getattr(api, "_FlightRadar24API__base_url", None)

    # Fallback: the endpoint is typically hosted at data-live.flightradar24.com
    # The wrapper may call something like /zones/fcgi/feed.js
    url = "https://data-live.flightradar24.com/zones/fcgi/feed.js"

    params = {
        "bounds": bounds,
        "faa": "1",
        "satellite": "1",
        "mlat": "1",
        "flarm": "1",
        "adsb": "1",
        "gnd": "1",
        "air": "1",
        "vehicles": "1",
        "estimated": "1",
        "maxage": "14400",
        "gliders": "1",
        "stats": "1",
        "limit": "5000",
    }

    import requests
    # Use a normal requests call with a browser-ish UA
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux armv7l) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://www.flightradar24.com/",
        "Origin": "https://www.flightradar24.com",
    }

    r = requests.get(url, params=params, headers=headers, timeout=20)

    ts = time.strftime("%Y%m%d_%H%M%S")
    out = Path("/tmp") / f"fr24_raw_feed_{ts}.txt"
    out.write_text(r.text)

    print("URL:", r.url)
    print("Status:", r.status_code)
    print("Content-Type:", r.headers.get("Content-Type"))
    print("Saved raw body ->", str(out))
    print("\n--- First 600 chars ---")
    print(r.text[:600])

    # If it looks like JSON, try parse keys
    try:
        j = r.json()
        print("\nParsed JSON top-level keys sample:", list(j.keys())[:30])
    except Exception:
        pass

if __name__ == "__main__":
    main()
