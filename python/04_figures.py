"""Figures, from committed and R-reconciled outputs only (team_seasons.csv,
league_seasons.csv). Plotly originals go to figures/; report_builder.py swaps
in the family's famplot engine at publish time, so only traces famplot draws
are used (scatter markers and lines, horizontal reference lines).

Figures:
  fig1_kill_vs_stop_py   kill rate against stop rate, every team-season, with
                         the kill rate independence predicts at each stop rate
  fig2_streak_z_py       observed against random-order kills by season: z,
                         with the +/-1.96 band
  fig3_kill_rate_py      league kill rate by season, observed and expected

Run:  python python/04_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

OUT = lib.ROOT / "output"
FIG = lib.ROOT / "figures"
LEAGUES = {"nba": "NBA", "wnba": "WNBA"}
COLORS = {"nba": "#2a78d6", "wnba": "#eb6834"}
GREY = "#898781"


def base_layout(title: str, xtitle: str, ytitle: str, height: int = 440) -> dict:
    return dict(title=title, xaxis_title=xtitle, yaxis_title=ytitle, template="plotly_white",
                height=height, margin=dict(l=70, r=30, t=60, b=60),
                legend=dict(orientation="h", y=-0.2))


def fig_scatter(ts: pl.DataFrame, summ: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    for lg, name in LEAGUES.items():
        r = ts.filter(pl.col("league") == lg)
        f.add_trace(go.Scatter(
            x=(r["stop_rate"] * 100).to_list(), y=r["kill_rate"].to_list(), mode="markers",
            name=name, marker=dict(size=7, color=COLORS[lg], opacity=0.6),
            customdata=list(zip(r["season"].to_list(), r["team"].to_list(), r["z_game"].to_list())),
            hovertemplate=f"{name} %{{customdata[0]}} %{{customdata[1]}}: stops %{{x:.1f}}%, "
                          "kills %{y:.2f} per 100 (z %{customdata[2]:.2f})<extra></extra>"))
    # Independence at each stop rate, for a 100-possession game.
    xs = [0.44 + i * 0.005 for i in range(29)]
    f.add_trace(go.Scatter(
        x=[100 * x for x in xs], y=[lib.expected_kills(100, x)[0] for x in xs], mode="lines",
        name="Independent possessions (100 a game)", line=dict(color=GREY, dash="dot"),
        hovertemplate="stops %{x:.1f}%: %{y:.2f} kills per 100<extra></extra>"))
    r2 = {r["league"]: r["r2_stop_kill"] for r in summ.iter_rows(named=True)}
    f.update_layout(**base_layout(f"Stop rate explains {r2['nba']:.0%} (NBA) and {r2['wnba']:.0%} "
                                  "(WNBA) of the variation in kill rate",
                                  "Opponent possessions ending in no points (%)",
                                  "Kills per 100 opponent possessions"))
    return f


def fig_z(ls: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    for lg, name in LEAGUES.items():
        r = ls.filter(pl.col("league") == lg).sort("year")
        f.add_trace(go.Scatter(
            x=r["year"].to_list(), y=r["z_game"].to_list(), mode="lines+markers", name=name,
            line=dict(color=COLORS[lg]), marker=dict(size=8, color=COLORS[lg]),
            customdata=list(zip(r["season"].to_list(), r["excess_game"].to_list())),
            hovertemplate=f"{name} %{{customdata[0]}}: z %{{y:.2f}} "
                          "(%{customdata[1]:+.0f} kills)<extra></extra>"))
    for y in (-1.96, 1.96):
        f.add_hline(y=y, line=dict(color="#c3c1bb", width=1, dash="dash"))
    f.add_hline(y=0, line=dict(color="#b5b3ad", width=1))
    f.update_layout(**base_layout(
        "Kills against each game's own stops in random order",
        "Season (starting year)", "z (observed minus expected kills)"))
    return f


def fig_rate(ls: pl.DataFrame) -> go.Figure:
    f = go.Figure()
    for lg, name in LEAGUES.items():
        r = ls.filter(pl.col("league") == lg).sort("year")
        f.add_trace(go.Scatter(
            x=r["year"].to_list(), y=r["kill_rate"].to_list(), mode="lines+markers",
            name=f"{name} observed", line=dict(color=COLORS[lg]), marker=dict(size=8, color=COLORS[lg]),
            hovertemplate=f"{name} %{{x}}: %{{y:.2f}} per 100<extra></extra>"))
        f.add_trace(go.Scatter(
            x=r["year"].to_list(), y=(100 * r["exp_game"] / r["opp_poss"]).to_list(), mode="lines",
            name=f"{name} random order", line=dict(color=COLORS[lg], dash="dot"),
            hovertemplate=f"{name} %{{x}} expected: %{{y:.2f}} per 100<extra></extra>"))
    f.update_layout(**base_layout("Kills per 100 opponent possessions, by season",
                                  "Season (starting year)", "Kills per 100"))
    return f


def main() -> None:
    FIG.mkdir(exist_ok=True)
    ts = pl.read_csv(OUT / "team_seasons.csv")
    ls = pl.read_csv(OUT / "league_seasons.csv")
    summ = pl.read_csv(OUT / "summary.csv")
    for name, fig in [("fig1_kill_vs_stop_py", fig_scatter(ts, summ)), ("fig2_streak_z_py", fig_z(ls)),
                      ("fig3_kill_rate_py", fig_rate(ls))]:
        fig.write_html(FIG / f"{name}.html", include_plotlyjs="cdn", full_html=True)
        fig.write_image(FIG / f"{name}.png", width=900, height=fig.layout.height or 440, scale=2)
        print("wrote", name)


if __name__ == "__main__":
    main()
