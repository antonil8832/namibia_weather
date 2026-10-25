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
TEMP, TEMP_BAR = "#eb6834", "#f6b08a"
RAIN = "#2a78d6"
WIND, GUST_BAR = "#2a78d6", "#b7d3f6"
# One-hue sequential ramps (light -> dark) for the overview heatmap
RAMPS = {
    "orange": ["#fdeee5", "#fad0b6", "#f5a77d", "#eb6834", "#c94f1d", "#963811", "#64250a"],
    "blue":   ["#eef5fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#2a78d6", "#1c5cab", "#104281"],
    "violet": ["#f1effb", "#d6d1f2", "#b2a9e6", "#8b7fd6", "#6556c2", "#4a3aa7", "#2e2370"],
}

TITLE = {"en": "Namibia Weather Monitor for the Antoniazzi - Manganelli expedition",
         "de": "Namibia-Wettermonitor für die Expedition Antoniazzi - Manganelli"}
MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

# Chart toolbar: only Home (reset), +, − and Autoscale; no drag/scroll/double-click/legend toggling
CONFIG = {"displaylogo": False, "responsive": True, "scrollZoom": False, "doubleClick": False,
          "modeBarButtons": [["resetScale2d", "zoomIn2d", "zoomOut2d", "autoScale2d"]]}


def load() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["ts"] = pd.to_datetime(df["obs_time_local"].fillna(df["run_timestamp_local"]))
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("ts")


def _vals(s, nd=1):
    return [None if pd.isna(v) else round(float(v), nd) for v in s]


def chart_data(df) -> dict:
    """Compact data for the browser: readings and one summary row per location and day."""
    readings, daily = {}, {}
    for loc in ORDER:
        s = df[df.location == loc]
        readings[loc] = {"t": s.ts.dt.strftime("%Y-%m-%dT%H:%M").tolist(),
                         "temp": _vals(s.temp_c), "wind": _vals(s.wind_kmh, 0),
                         "slot": s.slot.map(SLOT_LABEL).fillna("").tolist()}
        d = s.groupby("date").agg(tmin=("day_tmin_c", "last"), tmax=("day_tmax_c", "last"),
                                  rain=("day_precip_mm", "last"),
                                  gmax=("day_gust_max_kmh", "last")).reset_index()
        daily[loc] = {"d": d.date.dt.strftime("%Y-%m-%d").tolist(), "tmin": _vals(d.tmin),
                      "tmax": _vals(d.tmax), "rain": _vals(d.rain), "gmax": _vals(d.gmax, 0)}
    dates = sorted(df.date.dt.strftime("%Y-%m-%d").unique().tolist())
    return {"order": ORDER, "dates": dates, "readings": readings, "daily": daily}


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
    """Static overview for the GitHub app: daily min–max range per location, last 14 days."""
    import matplotlib.dates as mdates
    fig, axes = plt.subplots(3, 3, figsize=(13, 8.5), sharex=True, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    last = df.date.max()
    d = df[df.date > last - pd.Timedelta(days=14)]
    daily = d.groupby(["location", "date"]).agg(tmin=("day_tmin_c", "last"),
                                                tmax=("day_tmax_c", "last")).reset_index()
    for ax, loc in zip(axes.flat, ORDER):
        s = daily[daily.location == loc]
        ax.set_facecolor(SURFACE)
        ax.bar(s.date, s.tmax - s.tmin, bottom=s.tmin, width=0.7, color=TEMP_BAR,
               edgecolor=TEMP, linewidth=0.8)
        ax.set_title(loc, fontsize=11, color=INK, loc="left")
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=INK2, labelsize=8)
    for ax in axes[:, 0]:
        ax.set_ylabel("°C", color=INK2)
    for ax in axes[-1]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.autofmt_xdate()
    fig.suptitle("Namibia – daily min–max temperature, last 14 days", x=0.01,
                 ha="left", fontsize=14, color=INK)
    fig.text(0.01, 0.005, "Data: Open-Meteo.com (CC BY 4.0)", fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(OUT / "latest.png", dpi=110)
    plt.close(fig)


def L(en: str, de: str) -> str:
    """Bilingual text span; the language switch swaps its content."""
    return f'<span data-en="{escape(en)}" data-de="{escape(de)}">{escape(en)}</span>'


# Placeholders like @@NAME@@ are filled in by main(); the page is plain HTML/CSS/JS.
PAGE = r"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE_EN@@</title>
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#d9661f">
<meta name="apple-mobile-web-app-title" content="Namibia Weather">
<style>
:root { --surface:@@SURFACE@@; --ink:@@INK@@; --ink2:@@INK2@@; --grid:@@GRID@@; --chip:#f1f0ec; color-scheme: light; }
* { box-sizing: border-box; }
body { margin:0; background:var(--surface); color:var(--ink); font-family:Inter,system-ui,-apple-system,sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 48px; }
header { display:flex; gap:16px; align-items:flex-start; justify-content:space-between; }
.brand { display:flex; gap:14px; align-items:center; }
.brand img { width:56px; height:56px; border-radius:12px; flex:none; }
h1 { font-size:24px; margin:0 0 4px; } .sub { color:var(--ink2); margin:0 0 16px; font-size:14px; }
h2 { font-size:17px; margin:36px 0 4px; } .hint { color:var(--ink2); font-size:13px; margin:0 0 10px; }
.seg { display:inline-flex; flex-wrap:wrap; border:1px solid var(--grid); border-radius:9px; overflow:hidden; background:var(--surface); }
.seg button { border:0; border-right:1px solid var(--grid); background:transparent; color:var(--ink2); padding:8px 14px; font:inherit; font-size:14px; cursor:pointer; min-height:38px; }
.seg button:last-child { border-right:0; }
.seg button[aria-pressed="true"] { background:var(--ink); color:var(--surface); }
.lang button { padding:6px 12px; font-size:13px; min-height:32px; }
.controls { position:sticky; top:0; z-index:5; background:var(--surface); padding:10px 0; margin:0 0 4px;
  display:flex; gap:10px; align-items:center; flex-wrap:wrap; border-bottom:1px solid var(--grid); }
.controls .label { color:var(--ink2); font-size:13px; }
.row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin:8px 0 6px; }
select { font:inherit; font-size:15px; padding:8px 34px 8px 12px; border:1px solid var(--grid); border-radius:9px; background:var(--surface);
  color:var(--ink); min-height:38px; appearance:none; -webkit-appearance:none;
  background-image:linear-gradient(45deg,transparent 50%,var(--ink2) 50%),linear-gradient(135deg,var(--ink2) 50%,transparent 50%);
  background-position:calc(100% - 18px) 55%, calc(100% - 13px) 55%; background-size:5px 5px; background-repeat:no-repeat; }
.tbl { overflow-x:auto; } table { border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }
th, td { text-align:right; padding:8px 10px; border-bottom:1px solid var(--grid); white-space:nowrap; }
th:first-child, td:first-child { text-align:left; position:sticky; left:0; background:var(--surface); } th { color:var(--ink2); font-weight:500; }
.flag { color:#9a5b00; font-size:12px; margin-left:6px; }
.chart { width:100%; } #fig-heat { min-height:380px; } .detail { min-height:300px; }
footer { color:var(--ink2); font-size:12px; margin-top:32px; }
@media (max-width:600px) { h1 { font-size:19px; } .brand img { width:44px; height:44px; } .seg button { padding:8px 11px; } }
</style>
<script src="@@PLOTLY_SRC@@" charset="utf-8"></script>
</head><body><main>
<header>
  <div class="brand"><img src="icon-192.png" alt="">
    <h1 data-en="@@TITLE_EN@@" data-de="@@TITLE_DE@@">@@TITLE_EN@@</h1></div>
  <div class="seg lang" role="group" aria-label="Language / Sprache">
    <button type="button" data-lang="en" aria-pressed="true">EN</button>
    <button type="button" data-lang="de" aria-pressed="false">DE</button>
  </div>
</header>
<p class="sub">@@SUB@@</p>

<div class="controls">
  <span class="label" data-en="Period" data-de="Zeitraum">Period</span>
  <div class="seg" id="period" role="group">
    <button type="button" data-period="7" data-en="Last 7 days" data-de="Letzte 7 Tage">Last 7 days</button>
    <button type="button" data-period="14" data-en="Last 2 weeks" data-de="Letzte 2 Wochen">Last 2 weeks</button>
    <button type="button" data-period="all" data-en="All data" data-de="Alle Daten">All data</button>
  </div>
</div>

<h2>@@H_LATEST@@</h2>
<div class="tbl"><table><thead><tr>@@THEAD@@</tr></thead>
<tbody>@@TABLE@@</tbody></table></div>

<h2 data-en="All locations, day by day" data-de="Alle Orte, Tag für Tag">All locations, day by day</h2>
<p class="hint" data-en="One cell per location and day; darker = higher. Tap a cell for the value."
   data-de="Eine Zelle pro Ort und Tag; dunkler = höher. Zelle antippen für den Wert.">One cell per location and day; darker = higher. Tap a cell for the value.</p>
<div class="row"><div class="seg" id="metric" role="group">
  <button type="button" data-metric="tmax" data-en="Max temp" data-de="Max. Temp.">Max temp</button>
  <button type="button" data-metric="tmin" data-en="Min temp" data-de="Min. Temp.">Min temp</button>
  <button type="button" data-metric="rain" data-en="Rain" data-de="Regen">Rain</button>
  <button type="button" data-metric="gmax" data-en="Max gusts" data-de="Max. Böen">Max gusts</button>
</div></div>
<div class="chart" id="fig-heat"></div>

<h2 data-en="Location detail" data-de="Ort im Detail">Location detail</h2>
<div class="row"><select id="loc" aria-label="Location / Ort"></select></div>
<div class="chart detail" id="fig-temp"></div>
<div class="chart detail" id="fig-rain"></div>
<div class="chart detail" id="fig-wind"></div>

<footer>@@FOOTER@@
<a href="https://github.com/antonil8832/namibia_weather/blob/main/data/namibia_weather.csv">data/namibia_weather.csv</a></footer>
</main>
<script>
const DATA = @@DATA@@;
const CONFIG = @@CONFIG@@;
const RAMPS = @@RAMPS@@;
const C = {surface:"@@SURFACE@@", ink:"@@INK@@", ink2:"@@INK2@@", grid:"@@GRID@@",
           temp:"@@TEMP@@", tempBar:"@@TEMP_BAR@@", rain:"@@RAIN@@", wind:"@@WIND@@", gustBar:"@@GUST_BAR@@"};
const DAY = 86400000;
const T = {
  en: { temp:"Temperature", tempRange:"Daily min–max temperature", reading:"Reading", rain:"Daily rainfall",
        wind:"Wind", gustMax:"Daily max gusts", windReading:"Wind at reading",
        min:"Min", max:"Max", gusts:"Max gusts", at:"at", dfmt:"%d %b", dfull:"%a %d %b %Y",
        metric:{tmax:"Max temperature (°C)", tmin:"Min temperature (°C)", rain:"Rainfall (mm)", gmax:"Max gusts (km/h)"} },
  de: { temp:"Temperatur", tempRange:"Tägliche Min–Max-Temperatur", reading:"Messung", rain:"Tägliche Niederschlagsmenge",
        wind:"Wind", gustMax:"Tägliche max. Böen", windReading:"Wind zur Messzeit",
        min:"Min", max:"Max", gusts:"Max. Böen", at:"um", dfmt:"%d. %b", dfull:"%a %d. %b %Y",
        metric:{tmax:"Max. Temperatur (°C)", tmin:"Min. Temperatur (°C)", rain:"Niederschlag (mm)", gmax:"Max. Böen (km/h)"} },
};
const METRIC = { tmax:{ramp:"orange", unit:"°C", nd:0}, tmin:{ramp:"orange", unit:"°C", nd:0},
                 rain:{ramp:"blue", unit:"mm", nd:1}, gmax:{ramp:"violet", unit:"km/h", nd:0} };

Plotly.register({moduleType:"locale", name:"de", dictionary:{
  "Zoom in":"Vergrößern", "Zoom out":"Verkleinern", "Autoscale":"Automatisch skalieren", "Reset axes":"Ansicht zurücksetzen"},
  format:{months:["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"],
    shortMonths:@@MONTHS_DE@@, days:["Sonntag","Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag"],
    shortDays:["So","Mo","Di","Mi","Do","Fr","Sa"], decimal:",", thousands:"."}});

const state = { lang:"en", period:"7", metric:"tmax", loc:DATA.order[0] };
const store = { get(k){ try { return localStorage.getItem(k); } catch(e) { return null; } },
                set(k,v){ try { localStorage.setItem(k,v); } catch(e) {} } };

function firstDate() {
  const n = state.period === "all" ? DATA.dates.length : Math.min(+state.period, DATA.dates.length);
  return DATA.dates[DATA.dates.length - n];
}
const ms = s => new Date(s + "T00:00:00Z").getTime();
const iso = t => new Date(t).toISOString().slice(0, 16);
function xRange() { return [iso(ms(firstDate())), iso(ms(DATA.dates[DATA.dates.length - 1]) + DAY)]; }
function nDays() { return DATA.dates.length - DATA.dates.indexOf(firstDate()); }
function rampScale(name) { const r = RAMPS[name]; return r.map((c, i) => [i / (r.length - 1), c]); }
function fmt(v, nd) { return v == null ? "–" : v.toLocaleString(state.lang === "de" ? "de-CH" : "en-GB", {minimumFractionDigits:nd, maximumFractionDigits:nd}); }

function baseLayout(title, ytitle, height) {
  return { title:{text:title, x:0, xanchor:"left", font:{size:15, color:C.ink}},
    height, paper_bgcolor:C.surface, plot_bgcolor:C.surface, dragmode:false, hovermode:"closest",
    font:{family:"Inter, system-ui, -apple-system, sans-serif", color:C.ink2, size:12},
    margin:{l:48, r:12, t:64, b:36}, bargap:0,
    legend:{orientation:"h", x:0, y:1.13, xanchor:"left", itemclick:false, itemdoubleclick:false, font:{size:12}},
    xaxis:{type:"date", range:xRange(), tickformat:T[state.lang].dfmt, showgrid:false, linecolor:C.grid, fixedrange:false},
    yaxis:{title:{text:ytitle}, gridcolor:C.grid, zeroline:false} };
}

function drawHeat() {
  const t = T[state.lang], m = METRIC[state.metric], from = firstDate();
  const dates = DATA.dates.filter(d => d >= from);
  const z = [], text = [];
  for (const loc of DATA.order) {
    const dl = DATA.daily[loc], idx = Object.fromEntries(dl.d.map((d, i) => [d, i]));
    const row = dates.map(d => (d in idx ? dl[state.metric][idx[d]] : null));
    z.push(row);
    text.push(row.map(v => (v == null || (state.metric === "rain" && v === 0)) ? "" : fmt(v, m.nd)));
  }
  const flat = z.flat().filter(v => v != null);
  let zmin = Math.min(...flat), zmax = Math.max(...flat);
  if (state.metric === "rain") { zmin = 0; zmax = Math.max(zmax, 5); }
  const el = document.getElementById("fig-heat");
  const plotW = Math.max(200, el.clientWidth - 112);
  const showText = plotW / Math.max(1, dates.length) >= 28;
  const height = 120 + DATA.order.length * 32;
  const trace = { type:"heatmap", x:dates, y:DATA.order, z, text, zmin, zmax,
    colorscale:rampScale(m.ramp), xgap:2, ygap:2, hoverongaps:false,
    texttemplate: showText ? "%{text}" : "", textfont:{size:11},
    colorbar:{thickness:10, len:0.9, outlinewidth:0, tickfont:{size:11}, title:{text:m.unit, side:"top", font:{size:11}}},
    hovertemplate:"<b>%{y}</b><br>%{x|" + t.dfull + "}<br>" + t.metric[state.metric].replace(/ \(.*\)/, "") + ": %{z:." + m.nd + "f} " + m.unit + "<extra></extra>" };
  const layout = { title:{text:t.metric[state.metric], x:0, xanchor:"left", font:{size:15, color:C.ink}},
    height, paper_bgcolor:C.surface, plot_bgcolor:C.surface, dragmode:false,
    font:{family:"Inter, system-ui, -apple-system, sans-serif", color:C.ink2, size:12},
    margin:{l:104, r:8, t:48, b:36},
    xaxis:{type:"date", tickformat:t.dfmt, showgrid:false, ticks:"", fixedrange:true},
    yaxis:{autorange:"reversed", showgrid:false, ticks:"", fixedrange:true, tickfont:{color:C.ink, size:12}} };
  Plotly.react(el, [trace], layout, Object.assign({locale:state.lang}, CONFIG, {displayModeBar:false}));
}

function drawDetail() {
  const t = T[state.lang], loc = state.loc, from = firstDate();
  // Hide the per-reading dots when a day gets narrower than ~30 px (phone + long periods)
  const many = (document.getElementById("fig-temp").clientWidth - 60) / nDays() < 30;
  const dl = DATA.daily[loc], rd = DATA.readings[loc];
  const di = dl.d.map((d, i) => i).filter(i => dl.d[i] >= from);
  const ri = rd.t.map((x, i) => i).filter(i => rd.t[i].slice(0, 10) >= from);
  const noon = di.map(i => dl.d[i] + "T12:00");
  const W = 0.62 * DAY;
  const cfg = Object.assign({locale:state.lang}, CONFIG);

  // Temperature: one bar per day from min to max, readings as dots inside the bar
  const tmin = di.map(i => dl.tmin[i]), tmax = di.map(i => dl.tmax[i]);
  const tempTraces = [{ type:"bar", name:t.tempRange, x:noon, base:tmin,
      y:di.map((_, k) => (tmax[k] == null || tmin[k] == null) ? null : +(tmax[k] - tmin[k]).toFixed(1)),
      width:W, marker:{color:C.tempBar, line:{width:0}}, customdata:di.map((_, k) => [tmin[k], tmax[k]]),
      hovertemplate:"%{x|" + t.dfull + "}<br>" + t.min + " %{customdata[0]:.1f} °C · " + t.max + " %{customdata[1]:.1f} °C<extra></extra>" }];
  if (!many) tempTraces.push({ type:"scatter", mode:"markers", name:t.reading, x:ri.map(i => rd.t[i]), y:ri.map(i => rd.temp[i]),
      marker:{color:C.temp, size:8, line:{color:C.surface, width:2}}, customdata:ri.map(i => rd.slot[i]),
      hovertemplate:"%{x|" + t.dfull + "}, %{customdata}<br>%{y:.1f} °C<extra></extra>" });
  const lt = baseLayout((many ? t.tempRange : t.temp) + " – " + loc, "°C", 320);
  if (many) lt.showlegend = false;
  Plotly.react("fig-temp", tempTraces, lt, cfg);

  // Rain: one bar per day
  const rain = di.map(i => dl.rain[i]);
  const lr = baseLayout(t.rain + " – " + loc, "mm", 260);
  lr.showlegend = false;
  lr.yaxis.range = [0, Math.max(2, ...rain.filter(v => v != null)) * 1.15];
  Plotly.react("fig-rain", [{ type:"bar", name:t.rain, x:noon, y:rain, width:W, marker:{color:C.rain},
      hovertemplate:"%{x|" + t.dfull + "}<br>%{y:.1f} mm<extra></extra>" }], lr, cfg);

  // Wind: daily max gust as bar, wind speed at each reading as dots
  const gmax = di.map(i => dl.gmax[i]);
  const windTraces = [{ type:"bar", name:t.gustMax, x:noon, y:gmax, width:W, marker:{color:C.gustBar},
      hovertemplate:"%{x|" + t.dfull + "}<br>" + t.gusts + " %{y:.0f} km/h<extra></extra>" }];
  if (!many) windTraces.push({ type:"scatter", mode:"markers", name:t.windReading, x:ri.map(i => rd.t[i]), y:ri.map(i => rd.wind[i]),
      marker:{color:C.wind, size:8, line:{color:C.surface, width:2}}, customdata:ri.map(i => rd.slot[i]),
      hovertemplate:"%{x|" + t.dfull + "}, %{customdata}<br>%{y:.0f} km/h<extra></extra>" });
  const lw = baseLayout((many ? t.gustMax : t.wind) + " – " + loc, "km/h", 320);
  lw.yaxis.rangemode = "tozero";
  if (many) lw.showlegend = false;
  Plotly.react("fig-wind", windTraces, lw, cfg);
}

function drawAll() { drawHeat(); drawDetail(); }

function press(groupId, attr, value) {
  document.querySelectorAll("#" + groupId + " button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset[attr] === value)));
}
function setLang(lang) {
  state.lang = lang;
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-en]").forEach(el => { el.textContent = el.dataset[lang]; });
  document.title = document.querySelector("h1").dataset[lang];
  document.querySelectorAll(".lang button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  store.set("lang", lang);
  drawAll();
}

const sel = document.getElementById("loc");
for (const loc of DATA.order) { const o = document.createElement("option"); o.value = o.textContent = loc; sel.appendChild(o); }

document.querySelectorAll(".lang button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));
document.querySelectorAll("#period button").forEach(b => b.addEventListener("click", () => {
  state.period = b.dataset.period; press("period", "period", state.period); store.set("period", state.period); drawAll(); }));
document.querySelectorAll("#metric button").forEach(b => b.addEventListener("click", () => {
  state.metric = b.dataset.metric; press("metric", "metric", state.metric); store.set("metric", state.metric); drawHeat(); }));
sel.addEventListener("change", () => { state.loc = sel.value; store.set("loc", state.loc); drawDetail(); });
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawAll, 200); });

// Restore the viewer's last choices
const sp = store.get("period"); if (["7", "14", "all"].includes(sp)) state.period = sp;
const sm = store.get("metric"); if (sm in METRIC) state.metric = sm;
const sl = store.get("loc"); if (DATA.order.includes(sl)) state.loc = sl;
sel.value = state.loc; press("period", "period", state.period); press("metric", "metric", state.metric);
let startLang = store.get("lang") || ((navigator.language || "").toLowerCase().startsWith("de") ? "de" : "en");
setLang(startLang === "de" ? "de" : "en");
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
    now = datetime.now(TZ)
    n = df.date.nunique()
    upd_en = now.strftime("%d %b %Y, %H:%M")
    upd_de = f"{now.day:02d}. {MONTHS_DE[now.month - 1]} {now.year}, {now:%H:%M}"
    sub = L(f"Readings 4× daily at 06:00, 12:00, 15:00 and 19:00 Windhoek time · last updated {upd_en} · {n} days of data",
            f"Messungen 4× täglich um 06:00, 12:00, 15:00 und 19:00 Uhr Windhoeker Zeit · zuletzt aktualisiert {upd_de} · Daten aus {n} Tagen")
    js = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")  # noqa: E731
    values = {
        "TITLE_EN": escape(TITLE["en"]), "TITLE_DE": escape(TITLE["de"]),
        "SURFACE": SURFACE, "INK": INK, "INK2": INK2, "GRID": GRID,
        "TEMP": TEMP, "TEMP_BAR": TEMP_BAR, "RAIN": RAIN, "WIND": WIND, "GUST_BAR": GUST_BAR,
        "PLOTLY_SRC": f"https://cdn.plot.ly/plotly-{plotly.offline.get_plotlyjs_version()}.min.js",
        "SUB": sub, "H_LATEST": L("Latest readings", "Aktuelle Messwerte"),
        "THEAD": "".join(f"<th>{L(en, de)}</th>" for en, de in HEAD),
        "TABLE": latest_table(df),
        "FOOTER": L("Values are model analyses from Open-Meteo.com (CC BY 4.0), not station measurements. Raw data:",
                    "Werte sind Modellanalysen von Open-Meteo.com (CC BY 4.0), keine Stationsmessungen. Rohdaten:"),
        "DATA": js(chart_data(df)), "CONFIG": js(CONFIG), "RAMPS": js(RAMPS), "MONTHS_DE": js(MONTHS_DE),
    }
    html = PAGE
    for k, v in values.items():
        html = html.replace(f"@@{k}@@", v)
    assert "@@" not in html, "unfilled placeholder"
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
