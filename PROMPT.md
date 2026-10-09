# Namibia Weather Monitor – agent prompt

Use this prompt for any agent (or person) that sets up, runs or maintains the monitor.
The repository already contains a working implementation of everything described here.

```
ROLE
You maintain an automated weather-monitoring pipeline in the GitHub repository
antonil8832/namibia_weather. Four times a day it collects current weather data for
fixed locations in Namibia, appends it to a CSV file in the repository, and rebuilds
an interactive dashboard and a static chart. Runs are unattended: never ask questions,
take the most reasonable choice and record it in data/run_log.txt.

SCHEDULER
GitHub Actions workflow .github/workflows/update-weather.yml, cron "7,37 4-17 * * *"
(UTC) = every 30 minutes from 06:07 to 19:37 Windhoek time (UTC+2 all year).
GitHub may delay or drop individual scheduled runs, so each slot gets several chances.
The slot is derived from the actual Windhoek time: nearest of
  06:00 early_morning · 12:00 midday · 15:00 peak · 19:00 evening
within ±90 minutes, otherwise "adhoc". Scheduled runs (--scheduled) record a slot only
if it has no reading yet that day and otherwise exit in seconds without committing.
Primary trigger: a Claude scheduled task ("Namibia weather – trigger readings") starts the
workflow via workflow_dispatch at 06:05, 12:05, 15:05 and 19:05 Windhoek time, because
GitHub's cron proved unreliable (most scheduled runs were never started). The GitHub cron
stays as a backup.
Manual run (Actions tab → "Update Namibia weather" → Run workflow) always records a
reading, replacing that day's reading for the same slot.

LOCATIONS (name, latitude, longitude, climate zone)
  Windhoek        -22.56, 17.08   Central highlands
  Walvis Bay      -22.96, 14.51   Coastal (fog, cold Benguela current)
  Swakopmund      -22.68, 14.53   Coastal
  Lüderitz        -26.65, 15.16   Southern coast (strong winds)
  Sesriem         -24.49, 15.80   Namib Desert
  Keetmanshoop    -26.58, 18.13   South, arid
  Okaukuejo       -19.18, 15.92   Etosha
  Rundu           -17.92, 19.77   North-east, Kavango
  Katima Mulilo   -17.50, 24.27   Zambezi, wettest region
To add or remove a location, edit LOCATIONS in scripts/fetch_weather.py and ORDER in
scripts/make_charts.py (keep both lists identical; the dashboard grid is 3×3).

DATA SOURCE
Open-Meteo forecast API (free, no key, CC BY 4.0), one request for all locations:
  https://api.open-meteo.com/v1/forecast?latitude=<lats>&longitude=<lons>
    &current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,
             rain,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,
             wind_gusts_10m,weather_code
    &daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_gusts_10m_max
    &timezone=Africa/Windhoek&wind_speed_unit=kmh&forecast_days=1
Values are model analyses, not station measurements. Optional extension: airport
METAR observations (FYWH, FYWB, FYKT, FYRU, FYLZ, FYKM) from
https://aviationweather.gov/api/data/metar?ids=<ICAO>&format=json, stored in the
same CSV with source="metar".

STORAGE – data/namibia_weather.csv (in the repository, committed every run)
One row per location per run. Columns, in order:
  run_timestamp_local, obs_time_local, date, slot, location, lat, lon, source,
  temp_c, feels_like_c, humidity_pct, precip_mm, rain_mm, cloud_pct, pressure_hpa,
  wind_kmh, wind_dir_deg, wind_gust_kmh, weather_code,
  day_tmax_c, day_tmin_c, day_precip_mm, day_gust_max_kmh, quality_flag
Rules: create with header if missing; append only, never delete history; if a row with
the same date + slot + location + source exists, replace it (ad hoc rows are always
kept); copy the file to data/namibia_weather_backup.csv before writing. Git history
is the full audit trail.

DATA QUALITY
quality_flag = "ok", or the reason when a value is missing or outside:
  temperature -10…50 °C, humidity 0…100 %, pressure 950…1050 hPa,
  wind/gusts 0…150 km/h, precipitation 0…300 mm, cloud 0…100 %.
Keep flagged rows; never invent or interpolate values.
API failure: 3 attempts, 30 s apart; then write no rows, log the error, still rebuild
charts from existing data, and let the workflow run show as failed (GitHub e-mails
the repository owner).

CHARTS – rebuilt from the full CSV after every run
docs/index.html (published via GitHub Pages), default window last 14 days, zoomable:
  1. Latest readings table: one row per location, flagged values marked.
  2. Temperature: 3×3 small multiples (one panel per location, shared axes), readings
     as line + markers, shaded daily min–max band.
  3. Daily rainfall: 3×3 small multiples, bars, axis from zero.
  4. Wind speed (solid) and gusts (dotted): 3×3 small multiples.
docs/latest.png: static 3×3 temperature chart, last 14 days.
Units on every axis, hover tooltips, footer "Data: Open-Meteo.com (CC BY 4.0)" and the
last update time in Windhoek time.

OUTPUT OF EACH RUN
  - Updated data/namibia_weather.csv, data/run_log.txt
  - Updated docs/index.html, docs/latest.png
  - One commit "Weather update <date time> Windhoek"
```
