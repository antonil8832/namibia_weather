#!/usr/bin/env python3
"""Build the dashboard (docs/index.html) and a static chart (docs/latest.png) from the CSV."""
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
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
        legend=dict(orientation="h", y=1.09, x=0, xanchor="left"),
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


def temperature_fig(df):
    fig = facet_fig("Temperature at each reading, with daily min–max range", "°C")
    daily = df.groupby(["location", "date"]).agg(tmax=("day_tmax_c", "last"),
                                                 tmin=("day_tmin_c", "last")).reset_index()
    for i, loc in enumerate(ORDER):
        r, c = pos(i)
        d = daily[daily.location == loc]
        x = d["date"] + pd.Timedelta(hours=12)
        fig.add_trace(go.Scatter(x=x, y=d.tmax, mode="lines", line=dict(width=0),
                                 showlegend=False, hoverinfo="skip"), r, c)
        fig.add_trace(go.Scatter(x=x, y=d.tmin, mode="lines", line=dict(width=0),
                                 fill="tonexty", fillcolor=BAND, name="Daily min–max",
                                 showlegend=(i == 0), legendgroup="band",
                                 customdata=d[["tmin", "tmax"]],
                                 hovertemplate="Daily range %{customdata[0]:.1f}–%{customdata[1]:.1f} °C<extra></extra>"), r, c)
        s = df[df.location == loc]
        fig.add_trace(go.Scatter(x=s.ts, y=s.temp_c, mode="lines+markers", name="Reading",
                                 line=dict(color=TEMP, width=2), marker=dict(size=7),
                                 showlegend=(i == 0), legendgroup="reading",
                                 customdata=s.slot.map(SLOT_LABEL),
                                 hovertemplate="%{y:.1f} °C (%{customdata} slot)<extra></extra>"), r, c)
    return fig


def rain_fig(df):
    fig = facet_fig("Daily rainfall", "mm")
    daily = df.groupby(["location", "date"])["day_precip_mm"].last().reset_index()
    for i, loc in enumerate(ORDER):
        r, c = pos(i)
        d = daily[daily.location == loc]
        fig.add_trace(go.Bar(x=d.date, y=d.day_precip_mm, marker_color=RAIN, name="Rainfall",
                             showlegend=False,
                             hovertemplate="%{y:.1f} mm<extra></extra>"), r, c)
    fig.update_yaxes(rangemode="tozero")
    return fig


def wind_fig(df):
    fig = facet_fig("Wind speed and gusts", "km/h")
    for i, loc in enumerate(ORDER):
        r, c = pos(i)
        s = df[df.location == loc]
        fig.add_trace(go.Scatter(x=s.ts, y=s.wind_kmh, mode="lines+markers", name="Wind",
                                 line=dict(color=WIND, width=2), marker=dict(size=7),
                                 showlegend=(i == 0), legendgroup="wind",
                                 hovertemplate="Wind %{y:.0f} km/h<extra></extra>"), r, c)
        fig.add_trace(go.Scatter(x=s.ts, y=s.wind_gust_kmh, mode="lines", name="Gusts",
                                 line=dict(color=GUST, width=2, dash="dot"),
                                 showlegend=(i == 0), legendgroup="gust",
                                 hovertemplate="Gusts %{y:.0f} km/h<extra></extra>"), r, c)
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
        flag = "" if r.quality_flag == "ok" else f' <span class="flag" title="{escape(str(r.quality_flag))}">⚠ check</span>'
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


PAGE = """<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Namibia Weather Monitor</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {{ --surface:{surface}; --ink:{ink}; --ink2:{ink2}; --grid:{grid}; color-scheme: light; }}
body {{ margin:0; background:var(--surface); color:var(--ink); font-family:Inter,system-ui,sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:24px; margin:0 0 4px; }} .sub {{ color:var(--ink2); margin:0 0 24px; font-size:14px; }}
h2 {{ font-size:16px; margin:32px 0 8px; }}
.tbl {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }}
th, td {{ text-align:right; padding:8px 10px; border-bottom:1px solid var(--grid); white-space:nowrap; }}
th:first-child, td:first-child {{ text-align:left; }} th {{ color:var(--ink2); font-weight:500; }}
.flag {{ color:#9a5b00; font-size:12px; margin-left:6px; }}
.card {{ margin-top:8px; }} footer {{ color:var(--ink2); font-size:12px; margin-top:32px; }}
</style></head><body><main>
<h1>Namibia Weather Monitor</h1>
<p class="sub">Readings 4× daily at 06:00, 12:00, 15:00 and 19:00 Windhoek time · last updated {updated} · {n_days} days of data</p>
<h2>Latest readings</h2>
<div class="tbl"><table><thead><tr><th>Location</th><th>Temp °C</th><th>Day min / max °C</th><th>Humidity %</th>
<th>Rain today mm</th><th>Wind km/h</th><th>Gusts km/h</th><th>Cloud %</th><th>Observed</th></tr></thead>
<tbody>{table}</tbody></table></div>
<div class="card">{temp}</div><div class="card">{rain}</div><div class="card">{wind}</div>
<footer>Values are model analyses from Open-Meteo.com (CC BY 4.0), not station measurements.
Raw data: <a href="https://github.com/antonil8832/namibia_weather/blob/main/data/namibia_weather.csv">data/namibia_weather.csv</a></footer>
</main></body></html>"""


def main():
    OUT.mkdir(exist_ok=True)
    if not CSV_PATH.exists():
        print("No data file yet; skipping charts.")
        return
    df = load()
    cfg = {"displaylogo": False, "responsive": True}
    since = df.ts.max() - pd.Timedelta(days=14)
    figs = []
    for fn in (temperature_fig, rain_fig, wind_fig):
        fig = fn(df)
        fig.update_xaxes(range=[since, df.ts.max() + pd.Timedelta(hours=6)])
        figs.append(fig.to_html(full_html=False, include_plotlyjs=False, config=cfg))
    html = PAGE.format(surface=SURFACE, ink=INK, ink2=INK2, grid=GRID,
                       updated=datetime.now(TZ).strftime("%d %b %Y, %H:%M"),
                       n_days=df.date.nunique(), table=latest_table(df),
                       temp=figs[0], rain=figs[1], wind=figs[2])
    (OUT / "index.html").write_text(html, encoding="utf-8")
    static_png(df)
    print(f"Charts written: {OUT/'index.html'}, {OUT/'latest.png'}")


if __name__ == "__main__":
    main()
