#!/usr/bin/env python3
import json
import os
import sys
import time
import math
import argparse
from pathlib import Path

# Make repo imports work when running from anywhere
REPO_ROOT = Path("/home/pskillman/pi/FlightTracker")
sys.path.insert(0, str(REPO_ROOT))

from FlightRadar24.api import FlightRadar24API

def to_dict(obj):
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {"repr": repr(obj)}

def dump_json(label, payload, out_dir="/tmp"):
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = Path(out_dir) / f"fr24_{label}_{ts}.json"
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return str(path)

def haversine_miles(lat1, lon1, lat2, lon2):
    # great-circle distance
    R = 3958.7613
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def zone_to_bounds_str(zone):
    """
    Accepts either:
      - a dict with tl_y, tl_x, br_y, br_x (as in FR24 zones), OR
      - a tuple/list already in (lat_min, lat_max, lon_min, lon_max), OR
      - a preformatted string "lat_min,lat_max,lon_min,lon_max"
    Returns bounds string expected by your FlightRadar24 wrapper.
    """
    if isinstance(zone, str):
        return zone
    if isinstance(zone, (tuple, list)) and len(zone) == 4:
        lat_min, lat_max, lon_min, lon_max = zone
        return f"{lat_min},{lat_max},{lon_min},{lon_max}"
    if isinstance(zone, dict) and all(k in zone for k in ("tl_y","tl_x","br_y","br_x")):
        lat_max = zone["tl_y"]
        lat_min = zone["br_y"]
        lon_min = zone["tl_x"]
        lon_max = zone["br_x"]
        return f"{lat_min},{lat_max},{lon_min},{lon_max}"
    raise ValueError(f"Unrecognized zone format for bounds: {type(zone)} -> {zone}")

def pick_best_flight(flights, home_lat=None, home_lon=None):
    # Prefer closest to home if lat/lon exist; otherwise first flight.
    best = None
    best_dist = None

    for f in flights:
        d = to_dict(f)
        lat = d.get("latitude") or d.get("lat")
        lon = d.get("longitude") or d.get("lon")
        if home_lat is not None and home_lon is not None and lat is not None and lon is not None:
            try:
                dist = haversine_miles(float(home_lat), float(home_lon), float(lat), float(lon))
            except Exception:
                dist = None
            if dist is not None and (best_dist is None or dist < best_dist):
                best = f
                best_dist = dist

    return best or flights[0], best_dist

def main():
    ap = argparse.ArgumentParser(description="Dump full FR24 payload for the current/nearby flight (sidecar tool).")
    ap.add_argument("--out-dir", default="/tmp", help="Directory to write JSON dumps (default: /tmp)")
    ap.add_argument("--limit", type=int, default=25, help="How many flights to consider (default: 25)")
    ap.add_argument("--no-details", action="store_true", help="Only dump the summary flight object, skip details call")
    args = ap.parse_args()

    # Load config from your repo
    try:
        import config
    except Exception as e:
        print("❌ Could not import config.py from repo root.")
        raise

    zone_home = getattr(config, "ZONE_HOME", None)
    if zone_home is None:
        raise SystemExit("❌ config.ZONE_HOME is missing; can’t use your existing bounds.")

    bounds = zone_to_bounds_str(zone_home)

    min_alt = getattr(config, "MIN_ALTITUDE", None)
    home_lat = getattr(config, "HOME_LAT", None)
    home_lon = getattr(config, "HOME_LON", None)

    fr = FlightRadar24API()

    print(f"Using bounds: {bounds}")
    print(f"MIN_ALTITUDE: {min_alt}")
    print(f"HOME_LAT/LON: {home_lat}, {home_lon}")
    print("Fetching flights...")

    flights = fr.get_flights(bounds=bounds)  # your wrapper wants a string
    print(f"Flights returned: {len(flights)}")

    if not flights:
        # This is the same symptom you saw: 0 flights everywhere.
        # We still write a debug file so you can inspect what config we used.
        path = dump_json("no_flights_debug", {
            "bounds": bounds,
            "MIN_ALTITUDE": min_alt,
            "HOME_LAT": home_lat,
            "HOME_LON": home_lon,
            "note": "get_flights returned 0. If the display shows flights, the app may be using cached/previous state or a different data source."
        }, out_dir=args.out_dir)
        raise SystemExit(f"❌ No flights returned. Wrote debug context to {path}")

    # Optionally filter altitude if that field exists
    def altitude_of(f):
        d = to_dict(f)
        return d.get("altitude") or d.get("alt")

    if min_alt is not None:
        filtered = []
        for f in flights:
            alt = altitude_of(f)
            try:
                if alt is not None and float(alt) >= float(min_alt):
                    filtered.append(f)
            except Exception:
                pass
        if filtered:
            flights = filtered
            print(f"After MIN_ALTITUDE filter: {len(flights)}")

    flights = flights[: max(1, args.limit)]
    chosen, dist = pick_best_flight(flights, home_lat=home_lat, home_lon=home_lon)
    chosen_dict = to_dict(chosen)

    summary_path = dump_json("flight_summary", chosen_dict, out_dir=args.out_dir)
    print(f"✅ Wrote summary: {summary_path}")

    if dist is not None:
        print(f"Chosen flight distance (approx): {dist:.1f} miles")

    if args.no_details:
        return

    # Your installed library signature is get_flight_details(self, flight: Flight)
    print("Fetching flight details (full payload)...")
    details = fr.get_flight_details(chosen)

    details_path = dump_json("flight_details", details, out_dir=args.out_dir)
    print(f"✅ Wrote details: {details_path}")

    # Sometimes the flight object gets enriched after calling get_flight_details
    enriched_path = dump_json("flight_object_after_details", to_dict(chosen), out_dir=args.out_dir)
    print(f"✅ Wrote enriched flight object: {enriched_path}")

    if isinstance(details, dict):
        print("Details top-level keys:", sorted(details.keys()))

if __name__ == "__main__":
    main()
