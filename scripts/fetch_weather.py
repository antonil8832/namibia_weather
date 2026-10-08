#!/usr/bin/env python3
"""Fetch current weather for Namibian locations from Open-Meteo and append to the CSV.

Usage:
    python scripts/fetch_weather.py                # live fetch
    python scripts/fetch_weather.py --from-json x  # use a saved API response (testing)
"""
import argparse
import csv
import json
import shutil
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CSV_PATH = DATA / "namibia_weather.csv"
BACKUP_PATH = DATA / "namibia_weather_backup.csv"
LOG_PATH = DATA / "run_log.txt"
TZ = ZoneInfo("Africa/Windhoek")

LOCATIONS = [
    ("Windhoek", -22.56, 17.08),
    ("Walvis Bay", -22.96, 14.51),
    ("Swakopmund", -22.68, 14.53),
    ("Lüderitz", -26.65, 15.16),
    ("Sesriem", -24.49, 15.80),
    ("Keetmanshoop", -26.58, 18.13),
    ("Okaukuejo", -19.18, 15.92),
    ("Rundu", -17.92, 19.77),
    ("Katima Mulilo", -17.50, 24.27),
]

# Windhoek local times (UTC+2, no daylight saving)
SLOTS = [("early_morning", 6, 0), ("midday", 12, 0), ("peak", 15, 0), ("evening", 19, 0)]
SLOT_TOLERANCE = timedelta(minutes=90)

CURRENT_VARS = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "precipitation",
    "rain", "cloud_cover", "pressure_msl", "wind_speed_10m", "wind_direction_10m",
    "wind_gusts_10m", "weather_code",
]
DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_gusts_10m_max"]

COLUMNS = [
    "run_timestamp_local", "obs_time_local", "date", "slot", "location", "lat", "lon", "source",
    "temp_c", "feels_like_c", "humidity_pct", "precip_mm", "rain_mm", "cloud_pct", "pressure_hpa",
    "wind_kmh", "wind_dir_deg", "wind_gust_kmh", "weather_code",
    "day_tmax_c", "day_tmin_c", "day_precip_mm", "day_gust_max_kmh", "quality_flag",
]

PLAUSIBLE = {
    "temp_c": (-10, 50), "feels_like_c": (-20, 60), "humidity_pct": (0, 100),
    "pressure_hpa": (950, 1050), "wind_kmh": (0, 150), "wind_gust_kmh": (0, 150),
    "precip_mm": (0, 300), "rain_mm": (0, 300), "cloud_pct": (0, 100),
}


def log(msg: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} | {msg}\n")
    print(msg)


def current_slot(now: datetime) -> str:
    best, best_gap = "adhoc", SLOT_TOLERANCE
    for name, h, m in SLOTS:
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        gap = abs(now - target)
        if gap <= best_gap:
            best, best_gap = name, gap
    return best


def build_url() -> str:
    params = {
        "latitude": ",".join(str(l[1]) for l in LOCATIONS),
        "longitude": ",".join(str(l[2]) for l in LOCATIONS),
        "current": ",".join(CURRENT_VARS),
        "daily": ",".join(DAILY_VARS),
        "timezone": "Africa/Windhoek",
        "wind_speed_unit": "kmh",
        "forecast_days": 1,
    }
    return "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)


def fetch(retries: int = 3, wait: int = 30):
    url = build_url()
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "namibia-weather-monitor"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                time.sleep(wait)
    raise RuntimeError(f"API failed after {retries} attempts: {last_err}")


def quality(row: dict) -> str:
    issues = []
    for col, (lo, hi) in PLAUSIBLE.items():
        v = row.get(col)
        if v in (None, ""):
            issues.append(f"{col} missing")
        elif not (lo <= float(v) <= hi):
            issues.append(f"{col}={v} out of range")
    return "ok" if not issues else "; ".join(issues)


def to_rows(payload, now: datetime, slot: str):
    results = payload if isinstance(payload, list) else [payload]
    if len(results) != len(LOCATIONS):
        raise RuntimeError(f"Expected {len(LOCATIONS)} locations, got {len(results)}")
    rows = []
    for (name, lat, lon), res in zip(LOCATIONS, results):
        c, d = res.get("current", {}), res.get("daily", {})
        first = lambda key: (d.get(key) or [None])[0]  # noqa: E731
        obs = c.get("time", "")
        row = {
            "run_timestamp_local": now.strftime("%Y-%m-%d %H:%M"),
            "obs_time_local": obs.replace("T", " "),
            "date": now.strftime("%Y-%m-%d"),
            "slot": slot,
            "location": name, "lat": lat, "lon": lon, "source": "open-meteo",
            "temp_c": c.get("temperature_2m"),
            "feels_like_c": c.get("apparent_temperature"),
            "humidity_pct": c.get("relative_humidity_2m"),
            "precip_mm": c.get("precipitation"),
            "rain_mm": c.get("rain"),
            "cloud_pct": c.get("cloud_cover"),
            "pressure_hpa": c.get("pressure_msl"),
            "wind_kmh": c.get("wind_speed_10m"),
            "wind_dir_deg": c.get("wind_direction_10m"),
            "wind_gust_kmh": c.get("wind_gusts_10m"),
            "weather_code": c.get("weather_code"),
            "day_tmax_c": first("temperature_2m_max"),
            "day_tmin_c": first("temperature_2m_min"),
            "day_precip_mm": first("precipitation_sum"),
            "day_gust_max_kmh": first("wind_gusts_10m_max"),
        }
        row = {k: ("" if v is None else v) for k, v in row.items()}
        row["quality_flag"] = quality(row)
        rows.append(row)
    return rows


def write_rows(new_rows):
    DATA.mkdir(parents=True, exist_ok=True)
    existing = []
    if CSV_PATH.exists():
        shutil.copyfile(CSV_PATH, BACKUP_PATH)
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    key = lambda r: (r["date"], r["slot"], r["location"], r["source"])  # noqa: E731
    new_keys = {key({k: str(v) for k, v in r.items()}) for r in new_rows}
    # "adhoc" runs never replace each other: they are kept as separate rows
    kept = [r for r in existing if key(r) not in new_keys or r["slot"] == "adhoc"]
    replaced = len(existing) - len(kept)
    all_rows = kept + new_rows
    all_rows.sort(key=lambda r: (str(r["run_timestamp_local"]), str(r["location"])))
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in all_rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    return replaced


def slot_done(date: str, slot: str) -> bool:
    if not CSV_PATH.exists():
        return False
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return any(r["date"] == date and r["slot"] == slot and r["source"] == "open-meteo"
                   for r in csv.DictReader(f))


def set_output(name: str, value: str) -> None:
    """Pass a value to later GitHub Actions steps (no-op when run locally)."""
    import os
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", help="Use a saved API response instead of calling the API")
    ap.add_argument("--now", help="Override current time, e.g. '2026-10-08 15:10' (testing)")
    ap.add_argument("--scheduled", action="store_true",
                    help="Scheduled mode: only record a slot that has no reading yet today")
    args = ap.parse_args()

    now = datetime.now(TZ)
    if args.now:
        now = datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    slot = current_slot(now)

    if args.scheduled:
        reason = None
        if slot == "adhoc":
            reason = "outside all slot windows"
        elif slot_done(now.strftime("%Y-%m-%d"), slot):
            reason = f"slot {slot} already recorded today"
        if reason:
            print(f"Skipping: {reason}")
            set_output("updated", "false")
            return

    try:
        payload = json.loads(Path(args.from_json).read_text()) if args.from_json else fetch()
        rows = to_rows(payload, now, slot)
    except Exception as e:  # noqa: BLE001
        log(f"slot={slot} | ERROR | {e} | no rows written")
        sys.exit(1)

    replaced = write_rows(rows)
    set_output("updated", "true")
    flags = [f"{r['location']}: {r['quality_flag']}" for r in rows if r["quality_flag"] != "ok"]
    log(f"slot={slot} | rows={len(rows)} (replaced {replaced}) | flags={len(flags)}"
        + (f" [{' | '.join(flags)}]" if flags else ""))


if __name__ == "__main__":
    main()
