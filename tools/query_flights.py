#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Iterable


def parse_args():
    p = argparse.ArgumentParser(
        description="Query FlightTracker JSONL dump for recent flights."
    )
    p.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="Lookback window in minutes (default: 30)",
    )
    p.add_argument(
        "--airport",
        default="RDU",
        help="Filter flights where origin or destination matches this IATA (default: RDU). Use 'ANY' to disable.",
    )
    p.add_argument(
        "--path",
        default="/home/pskillman/pi/FlightTracker/logs/flight_api_dump.jsonl",
        help="Path to flight_api_dump.jsonl",
    )
    p.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Do not dedupe by flight id (show every observed row)",
    )
    return p.parse_args()


def iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Skip bad lines but keep going
                continue


def fmt_ts(ts: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone().strftime("%m/%d/%Y %H:%M:%S")
    except Exception:
        return ""


def main():
    args = parse_args()
    dump_path = Path(args.path)

    if not dump_path.exists():
        print(f"❌ Dump file not found: {dump_path}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now().timestamp()
    cutoff = now - (args.minutes * 60)

    airport = (args.airport or "").strip().upper()
    filter_airport = (airport != "" and airport != "ANY")

    # If dedupe: keep latest observation per flight id
    latest_by_id: Dict[str, Dict[str, Any]] = {}
    all_rows = []

    records_scanned = 0
    records_in_window = 0

    for rec in iter_jsonl(dump_path):
        records_scanned += 1
        ts = rec.get("ts")
        if ts is None:
            continue
        try:
            ts = int(ts)
        except Exception:
            continue

        if ts < cutoff:
            continue

        records_in_window += 1

        flights = rec.get("flights") or []
        for f in flights:
            if not isinstance(f, dict):
                continue

            # basic fields
            fid = str(f.get("id") or "")
            if not fid:
                # no id -> treat as unique row
                fid = f"NOID:{ts}:{f.get('callsign','')}:{f.get('registration','')}"

            ori = (f.get("origin_airport_iata") or "").upper()
            dst = (f.get("destination_airport_iata") or "").upper()

            if filter_airport and (ori != airport and dst != airport):
                continue

            row = dict(f)
            row["_ts"] = ts
            row["_ts_str"] = fmt_ts(ts)

            if args.no_dedupe:
                all_rows.append(row)
            else:
                prev = latest_by_id.get(fid)
                if prev is None or ts >= prev.get("_ts", 0):
                    latest_by_id[fid] = row

    rows = all_rows if args.no_dedupe else list(latest_by_id.values())
    rows.sort(key=lambda r: r.get("_ts", 0), reverse=True)

    # Print
    title_airport = airport if filter_airport else "ANY"
    print(f"✅ Flights in last {args.minutes} min (filter airport: {title_airport})")
    print(f"   Dump: {dump_path}")
    print(f"   Records scanned: {records_scanned}, in window: {records_in_window}")
    print()

    if not rows:
        print("No matching flights found.")
        return 0

    # Table header
    cols = [
        ("Time", "_ts_str"),
        ("ID", "id"),
        ("Callsign", "callsign"),
        ("Num", "number"),
        ("Reg", "registration"),
        ("Type", "aircraft_code"),
        ("From", "origin_airport_iata"),
        ("To", "destination_airport_iata"),
        ("Alt(ft)", "altitude"),
        ("GS", "ground_speed"),
        ("VS", "vertical_speed"),
        ("Lat", "latitude"),
        ("Lon", "longitude"),
    ]

    # column widths (lightweight)
    widths = []
    for label, key in cols:
        w = len(label)
        for r in rows[:200]:
            v = r.get(key, "")
            s = "" if v is None else str(v)
            if len(s) > w:
                w = min(len(s), 20)
        widths.append(w)

    def cell(s, w):
        s = "" if s is None else str(s)
        if len(s) > w:
            s = s[: max(0, w - 1)] + "…"
        return s.ljust(w)

    header = "  ".join(cell(label, widths[i]) for i, (label, _) in enumerate(cols))
    print(header)
    print("-" * len(header))

    for r in rows:
        line = "  ".join(
            cell(r.get(key, ""), widths[i]) for i, (_, key) in enumerate(cols)
        )
        print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())