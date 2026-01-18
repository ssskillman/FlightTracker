from FlightRadar24.api import FlightRadar24API
from threading import Thread, Lock
from datetime import datetime
from time import sleep
import math
import time

import config

from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError, MaxRetryError

# Optional non-blocking dumper (only used if enabled in config)
try:
    from utilities.flight_dump import FlightDumper
except Exception:
    FlightDumper = None


try:
    # Attempt to load config data
    from config import MIN_ALTITUDE
except (ModuleNotFoundError, NameError, ImportError):
    MIN_ALTITUDE = 0  # feet


RETRIES = 3
RATE_LIMIT_DELAY = 1
MAX_FLIGHT_LOOKUP = 5
MAX_ALTITUDE = 45000  # feet
EARTH_RADIUS_KM = 6371
BLANK_FIELDS = ["", "N/A", "NONE"]


try:
    # Attempt to load config data
    from config import ZONE_HOME, LOCATION_HOME

    ZONE_DEFAULT = ZONE_HOME
    LOCATION_DEFAULT = LOCATION_HOME

except (ModuleNotFoundError, NameError, ImportError):
    ZONE_DEFAULT = {"tl_y": 62.61, "tl_x": -13.07, "br_y": 49.71, "br_x": 3.46}
    LOCATION_DEFAULT = [51.509865, -0.118092, EARTH_RADIUS_KM]


# -----------------------------
# Helpers
# -----------------------------

def _safe_upper(s):
    try:
        return s.upper()
    except Exception:
        return ""


def _clean_blank(s):
    s = s or ""
    return "" if _safe_upper(s) in BLANK_FIELDS else s


def _get_in(d, path, default=""):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


def _airport_place(airport_dict):
    """
    Extract (iata, city, region/state-ish, country_code) from FR24 airport dict.
    FR24 varies, so be defensive.
    """
    iata = (
        _clean_blank(_get_in(airport_dict, ["code", "iata"], ""))
        or _clean_blank(_get_in(airport_dict, ["iata"], ""))
    )

    city = (
        _clean_blank(_get_in(airport_dict, ["position", "region", "city"], ""))
        or _clean_blank(_get_in(airport_dict, ["position", "city"], ""))
    )

    region = (
        _clean_blank(_get_in(airport_dict, ["position", "region", "region"], ""))
        or _clean_blank(_get_in(airport_dict, ["position", "region", "name"], ""))
        or _clean_blank(_get_in(airport_dict, ["position", "region", "code"], ""))
        or _clean_blank(_get_in(airport_dict, ["position", "region"], ""))  # sometimes it's just a string
    )

    country = (
        _clean_blank(_get_in(airport_dict, ["position", "country", "code"], ""))
        or _clean_blank(_get_in(airport_dict, ["position", "country", "name"], ""))
    )

    return iata, city, region, country


def _label(iata, city, region):
    parts = []
    if city:
        parts.append(city)
    if region:
        parts.append(region)
    place = ", ".join(parts).strip()
    if iata and place:
        return f"{iata} {place}"
    return iata or place or ""


def distance_from_flight_to_home(flight, home=LOCATION_DEFAULT):
    def polar_to_cartesian(lat, lon, alt):
        DEG2RAD = math.pi / 180
        return [
            alt * math.cos(DEG2RAD * lat) * math.sin(DEG2RAD * lon),
            alt * math.sin(DEG2RAD * lat),
            alt * math.cos(DEG2RAD * lat) * math.cos(DEG2RAD * lon),
        ]

    def feet_to_km_plus_earth(altitude_ft):
        altitude_km = 0.0003048 * altitude_ft
        return altitude_km + EARTH_RADIUS_KM

    try:
        (x0, y0, z0) = polar_to_cartesian(
            flight.latitude,
            flight.longitude,
            feet_to_km_plus_earth(flight.altitude),
        )

        (x1, y1, z1) = polar_to_cartesian(*home)

        dist = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2)
        return dist

    except Exception:
        # on error say it's far away
        return 1e6


# -----------------------------
# Overhead
# -----------------------------

class Overhead:
    def __init__(self):
        self._api = FlightRadar24API()
        self._lock = Lock()
        self._data = []
        self._new_data = False
        self._processing = False

        # Optional non-blocking dump of the raw "flights list" payload
        self._dump_enabled = bool(getattr(config, "FLIGHT_DUMP_ENABLED", False))
        self._dump_interval = int(getattr(config, "FLIGHT_DUMP_INTERVAL_SEC", 30))
        self._dump_last_ts = 0

        self._flight_dumper = None
        if self._dump_enabled and FlightDumper is not None:
            dump_path = getattr(config, "FLIGHT_DUMP_PATH", "/tmp/flight_api_dump.jsonl")
            try:
                self._flight_dumper = FlightDumper(dump_path, flush_every=3.0, max_queue=10)
                self._flight_dumper.start()
            except Exception:
                self._flight_dumper = None

    def grab_data(self):
        Thread(target=self._grab_data, daemon=True).start()

    def _grab_data(self):
        # Mark data as old
        with self._lock:
            self._new_data = False
            self._processing = True

        data = []

        try:
            bounds = self._api.get_bounds(ZONE_DEFAULT)
            flights = self._api.get_flights(bounds=bounds)

            # ---- Optional dump: raw "list flights" payload (non-blocking)
            now = time.time()
            if self._flight_dumper and (now - self._dump_last_ts) >= self._dump_interval:
                def _to_dict(x):
                    if isinstance(x, dict):
                        return x
                    if hasattr(x, "__dict__"):
                        return dict(x.__dict__)
                    return {"repr": repr(x)}

                record = {
                    "ts": int(now),
                    "ts_iso": datetime.fromtimestamp(now).strftime("%m/%d/%Y %H:%M:%S"),
                    "bounds": bounds,
                    "count": len(flights),
                    "flights": [_to_dict(f) for f in flights],
                }
                try:
                    self._flight_dumper.submit(record)
                    self._dump_last_ts = now
                except Exception:
                    pass

            # Filter flights
            flights = [
                f for f in flights
                if f.altitude < MAX_ALTITUDE and f.altitude > MIN_ALTITUDE
            ]

            # Sort flights by closest first
            flights = sorted(flights, key=lambda f: distance_from_flight_to_home(f))

            for flight in flights[:MAX_FLIGHT_LOOKUP]:
                retries = RETRIES

                while retries:
                    # Rate limit protection
                    sleep(RATE_LIMIT_DELAY)

                    try:
                        details = self._api.get_flight_details(flight)

                        # Plane model
                        try:
                            plane = details["aircraft"]["model"]["text"]
                        except (KeyError, TypeError):
                            plane = ""
                        plane = _clean_blank(plane)

                        # Callsign
                        callsign = _clean_blank(getattr(flight, "callsign", ""))

                        # Basic IATA codes from flight object (fast path)
                        origin_iata = _clean_blank(getattr(flight, "origin_airport_iata", ""))
                        dest_iata = _clean_blank(getattr(flight, "destination_airport_iata", ""))

                        origin_city = origin_region = ""
                        dest_city = dest_region = ""

                        # Enrich from details payload
                        try:
                            origin_airport = _get_in(details, ["airport", "origin"], {})
                            dest_airport = _get_in(details, ["airport", "destination"], {})

                            oi, oc, orr, _ = _airport_place(origin_airport)
                            di, dc, drr, _ = _airport_place(dest_airport)

                            origin_iata = origin_iata or oi
                            dest_iata = dest_iata or di

                            origin_city, origin_region = oc, orr
                            dest_city, dest_region = dc, drr
                        except Exception:
                            pass

                        data.append(
                            {
                                "plane": plane,
                                "origin": origin_iata,
                                "destination": dest_iata,

                                # enriched fields
                                "origin_city": origin_city,
                                "origin_region": origin_region,
                                "destination_city": dest_city,
                                "destination_region": dest_region,

                                # friendly labels for UI
                                "origin_label": _label(origin_iata, origin_city, origin_region),
                                "destination_label": _label(dest_iata, dest_city, dest_region),

                                "vertical_speed": flight.vertical_speed,
                                "altitude": flight.altitude,
                                "callsign": callsign,
                            }
                        )
                        break

                    except (KeyError, AttributeError):
                        retries -= 1

            with self._lock:
                self._new_data = True
                self._processing = False
                self._data = data

        except (ConnectionError, NewConnectionError, MaxRetryError):
            with self._lock:
                self._new_data = False
                self._processing = False

    @property
    def new_data(self):
        with self._lock:
            return self._new_data

    @property
    def processing(self):
        with self._lock:
            return self._processing

    @property
    def data(self):
        with self._lock:
            self._new_data = False
            return self._data

    @property
    def data_is_empty(self):
        return len(self._data) == 0


# Main function
if __name__ == "__main__":
    o = Overhead()
    o.grab_data()
    while not o.new_data:
        print("processing...")
        sleep(1)

    print(o.data)
