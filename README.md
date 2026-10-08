# Namibia Weather Monitor

Collects current weather for 9 locations in Namibia four times a day
(06:00, 12:00, 15:00, 19:00 Windhoek time), stores it in `data/namibia_weather.csv`
and rebuilds an interactive dashboard (`docs/index.html`) and a static chart
(`docs/latest.png`). Everything runs on GitHub Actions; no server or API key needed.

Full specification: [PROMPT.md](PROMPT.md)

## One-time setup

1. Upload all files in this folder to the repository (keep the folder structure,
   including the hidden `.github` folder).
2. **Settings → Actions → General → Workflow permissions**: select
   *Read and write permissions* and save.
3. **Settings → Pages**: Source *Deploy from a branch*, branch `main`, folder `/docs`.
   The dashboard will be at `https://antonil8832.github.io/namibia_weather/`.
   (On a free account, GitHub Pages requires the repository to be public.)
4. **Actions tab → "Update Namibia weather" → Run workflow** for a first run.

## Files

| Path | Purpose |
|---|---|
| `.github/workflows/update-weather.yml` | Schedule (4× daily) and run steps |
| `scripts/fetch_weather.py` | Fetches Open-Meteo data, validates, appends to CSV |
| `scripts/make_charts.py` | Builds dashboard and PNG from the full CSV |
| `data/namibia_weather.csv` | All readings (created on first run) |
| `data/run_log.txt` | One line per run, including errors and quality flags |
| `docs/index.html`, `docs/latest.png` | Charts |

## Notes

- GitHub can delay scheduled runs by up to ~30–60 minutes at busy times; the slot
  logic tolerates ±90 minutes. GitHub may pause schedules in public repositories
  with no activity for 60 days; if that happens, re-enable the workflow in the Actions tab.
- Data: Open-Meteo.com (CC BY 4.0). Values are model analyses, not station measurements.
