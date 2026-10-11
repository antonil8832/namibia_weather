#!/usr/bin/env python3
"""Build the dashboard (docs/index.html) and a static chart (docs/latest.png) from the CSV."""
from datetime import datetime
import json
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import plotly
import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "namibia_weather.csv"
OUT = ROOT / "docs"
TZ = ZoneInfo("Africa/Windhoek")

ORDER = ["Windhoek", "Walvis Bay", "Swakopmund", "Lüderitz", "Sesriem",
         "Keetmanshoop", "Okaukuejo", "Rundu", "Katima Mulilo"]
SLOT_LABEL = {"early_morning": "06:00", "midday": "12:00", "peak": "15:00",
              "evening": "19:00", "adhoc": "ad hoc"}

# Colors (validated reference palette, light mode)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
TEMP, BAND = "#eb6834", "rgba(235,104,52,0.14)"
RAIN = "#2a78d6"
WIND, GUST = "#2a78d6", "#eb6834"

TITLE = {"en": "Namibia Weather Monitor for the Antoniazzi - Manganelli expedition",
         "de": "Namibia-Wettermonitor für die Expedition Antoniazzi - Manganelli"}
T = {
    "en": dict(
        temp_title="Temperature at each reading, with daily min–max range", band="Daily min–max",
        reading="Reading", range_hover="Daily range %{customdata[0]:.1f}–%{customdata[1]:.1f} °C",
        reading_hover="%{y:.1f} °C (%{customdata} slot)",
        rain_title="Daily rainfall", rain="Rainfall",
        wind_title="Wind speed and gusts", wind="Wind", gust="Gusts",
        wind_hover="Wind %{y:.0f} km/h", gust_hover="Gusts %{y:.0f} km/h",
        hoverformat="%d %b %Y, %H:%M"),
    "de": dict(
        temp_title="Temperatur je Messung, mit täglicher Min–Max-Spanne", band="Tages-Min–Max",
        reading="Messung", range_hover="Tagesspanne %{customdata[0]:.1f}–%{customdata[1]:.1f} °C",
        reading_hover="%{y:.1f} °C (Messzeit %{customdata})",
        rain_title="Tägliche Niederschlagsmenge", rain="Niederschlag",
        wind_title="Windgeschwindigkeit und Böen", wind="Wind", gust="Böen",
        wind_hover="Wind %{y:.0f} km/h", gust_hover="Böen %{y:.0f} km/h",
        hoverformat="%d.%m.%Y, %H:%M"),
}
MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# Chart toolbar: only Home (reset), +, − and Autoscale; no drag/scroll/double-click/legend toggling
CONFIG = {"displaylogo": False, "responsive": True, "scrollZoom": False, "doubleClick": False,
          "modeBarButtons": [["resetScale2d", "zoomIn2d", "zoomOut2d", "autoScale2d"]]}


def load() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["ts"] = pd.to_datetime(df["obs_time_local"].fillna(df["run_timestamp_local"]))
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("ts")


def facet_fig(title: str, y_title: str) -> go.Figure:
    fig = make_subplots(rows=3, cols=3, subplot_titles=ORDER, shared_xaxes=True,
                        shared_yaxes=True, vertical_spacing=0.09, horizontal_spacing=0.04)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=INK), x=0, xanchor="left"),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, height=640,
        margin=dict(l=56, r=16, t=90, b=40), hovermode="x unified",
        font=dict(family="Inter, system-ui, sans-serif", color=INK2, size=12),
        legend=dict(orientation="h", y=1.09, x=0, xanchor="left",
                    itemclick=False, itemdoubleclick=False),
        dragmode=False,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickformat="%d %b")
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    for r in range(1, 4):
        fig.update_yaxes(title_text=y_title, row=r, col=1)
    for a in fig.layout.annotations:
        a.font = dict(size=13, color=INK)
    return fig


def pos(i):
    return i // 3 + 1, i % 3 + 1


def temperature_fig(df, t):
    fig = facet_fig(t["temp_title"], "°C")
    daily = df.groupby(["location", "date"]).agg(tmax=("day_tmax_c", "last"),
                                                 tmin=("day_tmin_c", "last")).reset_index()
    for i, loc in enumerate(ORDER):
        r, c = pos(i)
        d = daily[daily.location == loc]
        x = d["date"] + pd.Timedelta(hours=12)
        fig.add_trace(go.Scatter(x=x, y=d.tmax, mode="lines", line=dict(width=0),
                                 showlegend=False, hoverinfo="skip"), r, c)
        fig.add_trace(go.Scatter(x=x, y=d.tmin, mode="lines", line=dict(width=0),
                                 fill="tonexty", fillcolor=BAND, name=t["band"],
                                 showlegend=(i == 0), legendgroup="band",
                                 customdata=d[["tmin", "tmax"]],
                                 hovertemplate=t["range_hover"] + "<extra></extra>"), r, c)
        s = df[df.location == loc]
        fig.add_trace(go.Scatter(x=s.ts, y=s.temp_c, mode="lines+markers", name=t["reading"],
                                 line=dict(color=TEMP, width=2), marker=dict(size=7),
                                 showlegend=(i == 0), legendgroup="reading",
                                 customdata=s.slot.map(SLOT_LABEL),
                                 hovertemplate=t["reading_hover"] + "<extra></extra>"), r, c)
    return fig


def rain_fig(df, t):
    fig = facet_fig(t["rain_title"], "mm")
    daily = df.groupby(["location", "date"])["day_precip_mm"].last().reset_index()
    for i, loc in enumerate(ORDER):
        r, c = pos(i)
        d = daily[daily.location == loc]
        fig.add_trace(go.Bar(x=d.date, y=d.day_precip_mm, marker_color=RAIN, name=t["rain"],
                             showlegend=False,
                             hovertemplate="%{y:.1f} mm<extra></extra>"), r, c)
    fig.update_yaxes(rangemode="tozero")
    return fig


def wind_fig(df, t):
    fig = facet_fig(t["wind_title"], "km/h")
    for i, loc in enumerate(ORDER):
        r, c = pos(i)
        s = df[df.location == loc]
        fig.add_trace(go.Scatter(x=s.ts, y=s.wind_kmh, mode="lines+markers", name=t["wind"],
                                 line=dict(color=WIND, width=2), marker=dict(size=7),
                                 showlegend=(i == 0), legendgroup="wind",
                                 hovertemplate=t["wind_hover"] + "<extra></extra>"), r, c)
        fig.add_trace(go.Scatter(x=s.ts, y=s.wind_gust_kmh, mode="lines", name=t["gust"],
                                 line=dict(color=GUST, width=2, dash="dot"),
                                 showlegend=(i == 0), legendgroup="gust",
                                 hovertemplate=t["gust_hover"] + "<extra></extra>"), r, c)
    fig.update_yaxes(rangemode="tozero")
    return fig


def latest_table(df) -> str:
    last_ts = df.groupby("location")["run_timestamp_local"].max()
    rows = []
    for loc in ORDER:
        if loc not in last_ts:
            continue
        r = df[(df.location == loc) & (df.run_timestamp_local == last_ts[loc])].iloc[-1]
        f = lambda v, n=1: "–" if pd.isna(v) else f"{v:.{n}f}"  # noqa: E731
        flag = "" if r.quality_flag == "ok" else f' <span class="flag" title="{escape(str(r.quality_flag))}">⚠ <span data-en="check" data-de="prüfen">check</span></span>'
        rows.append(
            f"<tr><td>{escape(loc)}{flag}</td><td>{f(r.temp_c)}</td><td>{f(r.day_tmin_c)} / {f(r.day_tmax_c)}</td>"
            f"<td>{f(r.humidity_pct,0)}</td><td>{f(r.day_precip_mm)}</td><td>{f(r.wind_kmh,0)}</td>"
            f"<td>{f(r.wind_gust_kmh,0)}</td><td>{f(r.cloud_pct,0)}</td><td>{escape(str(r.obs_time_local))}</td></tr>")
    return "\n".join(rows)


def static_png(df):
    fig, axes = plt.subplots(3, 3, figsize=(13, 8.5), sharex=True, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    since = df.ts.max() - pd.Timedelta(days=14)
    d = df[df.ts >= since]
    for ax, loc in zip(axes.flat, ORDER):
        s = d[d.location == loc]
        ax.set_facecolor(SURFACE)
        ax.plot(s.ts, s.temp_c, color=TEMP, lw=2, marker="o", ms=4)
        ax.set_title(loc, fontsize=11, color=INK, loc="left")
        ax.grid(axis="y", color=GRID, lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=INK2, labelsize=8)
    for ax in axes[:, 0]:
        ax.set_ylabel("°C", color=INK2)
    import matplotlib.dates as mdates
    for ax in axes[-1]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.autofmt_xdate()
    fig.suptitle("Namibia – temperature readings, last 14 days (Windhoek time)", x=0.01,
                 ha="left", fontsize=14, color=INK)
    fig.text(0.01, 0.005, "Data: Open-Meteo.com (CC BY 4.0)", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(OUT / "latest.png", dpi=110)
    plt.close(fig)


def L(en: str, de: str) -> str:
    """Bilingual text span; the language switch swaps its content."""
    return f'<span data-en="{escape(en)}" data-de="{escape(de)}">{escape(en)}</span>'


PAGE = """<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_en}</title>
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#d9661f">
<meta name="apple-mobile-web-app-title" content="Namibia Weather">
<style>
:root {{ --surface:{surface}; --ink:{ink}; --ink2:{ink2}; --grid:{grid}; color-scheme: light; }}
body {{ margin:0; background:var(--surface); color:var(--ink); font-family:Inter,system-ui,sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:24px 16px 48px; }}
header {{ display:flex; gap:16px; align-items:flex-start; justify-content:space-between; }}
.brand {{ display:flex; gap:14px; align-items:center; }}
.brand img {{ width:56px; height:56px; border-radius:12px; flex:none; }}
h1 {{ font-size:24px; margin:0 0 4px; }} .sub {{ color:var(--ink2); margin:0 0 24px; font-size:14px; }}
h2 {{ font-size:16px; margin:32px 0 8px; }}
.lang {{ display:flex; border:1px solid var(--grid); border-radius:8px; overflow:hidden; flex:none; }}
.lang button {{ border:0; background:transparent; color:var(--ink2); padding:6px 12px; font:inherit; font-size:13px; cursor:pointer; }}
.lang button[aria-pressed="true"] {{ background:var(--ink); color:var(--surface); }}
.tbl {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:right; padding:8px 10px; border-bottom:1px solid var(--grid); white-space:nowrap; }}
th:first-child, td:first-child {{ text-align:left; }} th {{ color:var(--ink2); font-weight:500; }}
.flag {{ color:#9a5b00; font-size:12px; margin-left:6px; }}
.card {{ margin-top:8px; min-height:640px; }} footer {{ color:var(--ink2); font-size:12px; margin-top:32px; }}
@media (max-width:600px) {{ h1 {{ font-size:19px; }} .brand img {{ width:44px; height:44px; }} }}
</style>
<script src="{plotly_src}" charset="utf-8"></script>
</head><body><main>
<header>
  <div class="brand"><img src="icon-192.png" alt="">
    <h1 data-en="{title_en}" data-de="{title_de}">{title_en}</h1></div>
  <div class="lang" role="group" aria-label="Language / Sprache">
    <button type="button" data-lang="en" aria-pressed="true">EN</button>
    <button type="button" data-lang="de" aria-pressed="false">DE</button>
  </div>
</header>
<p class="sub">{sub}</p>
<h2>{h_latest}</h2>
<div class="tbl"><table><thead><tr>{thead}</tr></thead>
<tbody>{table}</tbody></table></div>
<div class="card" id="fig-temp"></div><div class="card" id="fig-rain"></div><div class="card" id="fig-wind"></div>
<footer>{footer}
<a href="https://github.com/antonil8832/namibia_weather/blob/main/data/namibia_weather.csv">data/namibia_weather.csv</a></footer>
</main>
<script>
const FIGS = {figs};
const CONFIG = {config};
Plotly.register({{moduleType: "locale", name: "de", dictionary: {{
  "Zoom in": "Vergrößern", "Zoom out": "Verkleinern",
  "Autoscale": "Automatisch skalieren", "Reset axes": "Ansicht zurücksetzen"}},
  format: {{months: ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"],
    shortMonths: {months_de}, days: ["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"],
    shortDays: ["So","Mo","Di","Mi","Do","Fr","Sa"], decimal: ",", thousands: "."}}}});
function setLang(lang) {{
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-en]").forEach(el => {{ el.textContent = el.dataset[lang]; }});
  document.title = document.querySelector("h1").dataset[lang];
  document.querySelectorAll(".lang button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  for (const id of ["temp", "rain", "wind"]) {{
    const f = FIGS[lang][id];
    Plotly.react("fig-" + id, f.data, f.layout, Object.assign({{locale: lang}}, CONFIG));
  }}
  try {{ localStorage.setItem("lang", lang); }} catch (e) {{}}
}}
document.querySelectorAll(".lang button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));
let start = "en";
try {{ start = localStorage.getItem("lang") || ((navigator.language || "").toLowerCase().startsWith("de") ? "de" : "en"); }} catch (e) {{}}
setLang(start === "de" ? "de" : "en");
</script>
</body></html>"""

HEAD = [("Location", "Ort"), ("Temp °C", "Temp. °C"), ("Day min / max °C", "Tag min / max °C"),
        ("Humidity %", "Luftfeuchte %"), ("Rain today mm", "Regen heute mm"), ("Wind km/h", "Wind km/h"),
        ("Gusts km/h", "Böen km/h"), ("Cloud %", "Bewölkung %"), ("Observed", "Beobachtet")]


def main():
    OUT.mkdir(exist_ok=True)
    if not CSV_PATH.exists():
        print("No data file yet; skipping charts.")
        return
    df = load()
    figs = {}
    for lang, t in T.items():
        figs[lang] = {}
        for key, fn in (("temp", temperature_fig), ("rain", rain_fig), ("wind", wind_fig)):
            fig = fn(df, t)
            # Default view = autoscale: no fixed x range, y fits the data
            fig.update_xaxes(autorange=True, hoverformat=t["hoverformat"])
            fig.update_yaxes(autorange=True)  # explicit, otherwise matched y-axes start at a fixed -1..4
            figs[lang][key] = json.loads(fig.to_json())
    now = datetime.now(TZ)
    n = df.date.nunique()
    upd_en = now.strftime("%d %b %Y, %H:%M")
    upd_de = f"{now.day:02d}. {MONTHS_DE[now.month - 1]} {now.year}, {now:%H:%M}"
    sub = L(f"Readings 4× daily at 06:00, 12:00, 15:00 and 19:00 Windhoek time · last updated {upd_en} · {n} days of data",
            f"Messungen 4× täglich um 06:00, 12:00, 15:00 und 19:00 Uhr Windhoeker Zeit · zuletzt aktualisiert {upd_de} · Daten aus {n} Tagen")
    html = PAGE.format(
        surface=SURFACE, ink=INK, ink2=INK2, grid=GRID,
        title_en=escape(TITLE["en"]), title_de=escape(TITLE["de"]),
        plotly_src=f"https://cdn.plot.ly/plotly-{plotly.offline.get_plotlyjs_version()}.min.js",
        sub=sub, h_latest=L("Latest readings", "Aktuelle Messwerte"),
        thead="".join(f"<th>{L(en, de)}</th>" for en, de in HEAD),
        table=latest_table(df),
        footer=L("Values are model analyses from Open-Meteo.com (CC BY 4.0), not station measurements. Raw data:",
                 "Werte sind Modellanalysen von Open-Meteo.com (CC BY 4.0), keine Stationsmessungen. Rohdaten:"),
        figs=json.dumps(figs, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        config=json.dumps(CONFIG), months_de=json.dumps(MONTHS_DE, ensure_ascii=False))
    (OUT / "index.html").write_text(html, encoding="utf-8")
    manifest = {"name": TITLE["en"], "short_name": "Namibia Weather", "start_url": ".", "display": "standalone",
                "background_color": SURFACE, "theme_color": "#d9661f",
                "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                          {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]}
    (OUT / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    static_png(df)
    print(f"Charts written: {OUT/'index.html'}, {OUT/'latest.png'}")


if __name__ == "__main__":
    main()
