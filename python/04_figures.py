"""Figures and explainer diagrams, from committed outputs only. Every number
drawn, titled, or annotated is read from output/ or computed from it here.

Plotly originals go to figures/; report_builder.py swaps in the family's
famplot engine at publish time, so only what famplot draws is used (scatter
markers, lines, and toself bands; bars; horizontal and vertical line shapes;
text annotations without arrows).

Figures:
  fig1_kill_vs_stop_py   kill rate against stop rate, every team-season, with
                         the kill rate independence predicts at each stop rate
                         and each league's highest and lowest kill rate named
                         (team_seasons.csv, summary.csv)
  fig2_streak_z_py       observed against random-order kills by season: z,
                         with the +/-1.96 band and the seasons outside it named
                         (league_seasons.csv)
  fig3_kill_rate_py      league kill rate by season, observed and expected
                         (league_seasons.csv)
  fig4_perm_baseline_py  the NBA's top kill-rate team-season: the exact
                         distribution of its kills with each game's stops in a
                         random order, its observed kills, and what a
                         league-average kill rate would give over the same
                         possessions (perm_example.csv, team_seasons.csv,
                         league_seasons.csv)
  fig5_record_margin_py  the NBA record stop streak on its game's score margin
                         (record_game.csv, records.csv)
  fig6_leaders_py        the ten best NBA kill rates, observed and random
                         order, with each one's stop-rate rank (leaders.csv,
                         team_seasons.csv, summary.csv)
Diagrams (famdiagram, figures/<ref>.svg and <ref>_narrow.svg):
  dg_kill_rules          what counts as a kill, on a real stretch of
                         possessions (example_strip.csv)

Run:  python python/04_figures.py
"""
from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
import famdiagram  # noqa: E402  (basketball-analysis-tools, on sys.path via lib)

OUT = lib.ROOT / "output"
FIG = lib.ROOT / "figures"
LEAGUES = {"nba": "NBA", "wnba": "WNBA"}
COLORS = {"nba": "#2a78d6", "wnba": "#eb6834"}
GREY = "#898781"
BAND = "#c3c1bb"
INK2 = "#52514e"


def base_layout(title: str, xtitle: str, ytitle: str, height: int = 440) -> dict:
    return dict(title=title, xaxis_title=xtitle, yaxis_title=ytitle, template="plotly_white",
                height=height, margin=dict(l=70, r=30, t=60, b=60),
                legend=dict(orientation="h", y=-0.2))


def note(f: go.Figure, x, y, text: str, color: str = INK2, xanchor: str = "left",
         yanchor: str = "middle", xshift: int = 0, yshift: int = 0, **kw) -> None:
    f.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor=xanchor, yanchor=yanchor,
                     xshift=xshift, yshift=yshift, font=dict(color=color, size=12), **kw)


def long_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def clock(secs: float) -> str:
    s = int(secs)
    return f"{s // 60}:{s % 60:02d}"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---------------------------------------------------------------- fig1 to fig3

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
    # Name each league's highest and lowest kill rate. The cloud runs up the
    # diagonal, so a "best" label goes up and left of its point and a
    # "lowest" label down and right, into empty space; the named points are
    # redrawn solid so each label has a visible anchor.
    for lg, name in LEAGUES.items():
        r = ts.filter(pl.col("league") == lg).sort("kill_rate")
        lo, hi = r.row(0, named=True), r.row(-1, named=True)
        f.add_trace(go.Scatter(
            x=[100 * hi["stop_rate"], 100 * lo["stop_rate"]], y=[hi["kill_rate"], lo["kill_rate"]],
            mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(size=9, color=COLORS[lg], opacity=1)))
        hx, hy = 100 * hi["stop_rate"], hi["kill_rate"]
        if lg == "nba":
            # The NBA's best sits inside the WNBA cloud: move its label up and
            # left into the empty space above the diagonal, with a leader line.
            lx, ly = hx - 2.5, hy + 0.6
            f.add_trace(go.Scatter(x=[lx + 0.1, hx], y=[ly - 0.05, hy], mode="lines",
                                   showlegend=False, hoverinfo="skip",
                                   line=dict(color=COLORS[lg], width=1)))
            note(f, lx, ly, f"{name} best: {hi['season']} {hi['team']}", color=COLORS[lg],
                 xanchor="right", yanchor="middle")
        else:
            note(f, hx, hy, f"{name} best: {hi['season']} {hi['team']}",
                 color=COLORS[lg], xanchor="right", yanchor="bottom", xshift=-6, yshift=6)
        note(f, 100 * lo["stop_rate"], lo["kill_rate"], f"{name} lowest: {lo['season']} {lo['team']}",
             color=COLORS[lg], xanchor="left", yanchor="top", xshift=6, yshift=-6)
    r2 = {r["league"]: r["r2_stop_kill"] for r in summ.iter_rows(named=True)}
    f.update_layout(**base_layout(f"Kill rate is stop rate: it explains {r2['nba']:.0%} (NBA) and "
                                  f"{r2['wnba']:.0%} (WNBA) of the variation",
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
    z = 1.959963984540054
    for y in (-z, z):
        f.add_hline(y=y, line=dict(color=BAND, width=1, dash="dash"))
    f.add_hline(y=0, line=dict(color="#b5b3ad", width=1))
    yr = ls["year"]
    inside = math.erf(z / math.sqrt(2))
    note(f, yr.min(), z, f"\u00b1{z:.2f}: {inside:.0%} of seasons fall inside by chance alone",
         color=GREY, yanchor="bottom")
    out = ls.filter(pl.col("z_game").abs() > z).sort("year")
    for r in out.iter_rows(named=True):
        note(f, r["year"], r["z_game"], f"{r['season']}: z {r['z_game']:.2f}",
             color=COLORS[r["league"]], xanchor="center", yanchor="top", yshift=-8)
    n_out = out.height
    n_all = ls.height
    f.update_layout(**base_layout(
        f"Stops arrive in random order: {n_all - n_out} of {n_all} league-seasons sit inside "
        "the chance band", "Season (starting year)", "z (observed minus expected kills)"))
    f.update_yaxes(range=[min(-3.0, float(ls["z_game"].min()) - 0.6), 3.0])
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
    f.update_layout(**base_layout("Observed kill rates sit on top of the random-order lines "
                                  "in every season", "Season (starting year)", "Kills per 100"))
    return f


# ---------------------------------------------------------------- new figures

def fig_perm(pe: pl.DataFrame, ts: pl.DataFrame, ls: pl.DataFrame) -> go.Figure:
    """The NBA's top kill-rate team-season against its own stops shuffled."""
    row = pe.row(0, named=True)
    t = ts.filter((pl.col("league") == row["league"]) & (pl.col("season") == row["season"])
                  & (pl.col("team") == row["team"])).row(0, named=True)
    league_rate = ls.filter((pl.col("league") == t["league"]) & (pl.col("year") == t["year"])) \
                    .row(0, named=True)["kill_rate"]
    avg = league_rate * t["opp_poss"] / 100
    mean, sd = t["exp_game"], t["var_game"] ** 0.5
    # Show the distribution where it has visible mass, and keep the
    # league-average line on the chart.
    lo = min(mean - 4.5 * sd, avg - 0.5 * sd)
    shown = pe.filter((pl.col("kills") >= lo) & (pl.col("kills") <= mean + 4.5 * sd))
    pk = float(shown["prob"].max())
    c = COLORS[t["league"]]
    f = go.Figure()
    f.add_trace(go.Bar(
        x=shown["kills"].to_list(), y=(100 * shown["prob"]).to_list(),
        name="Kills with each game's stops in random order", marker=dict(color="#a9c8ee"),
        hovertemplate="%{x} kills: %{y:.2f}% of orderings<extra></extra>"))
    lname = LEAGUES[t["league"]]
    f.add_vline(x=t["kills"], line=dict(color=c, width=2.5))
    f.add_vline(x=avg, line=dict(color=GREY, width=1.5, dash="dash"))
    top = 100 * pk
    # Two short lines above the bars at the observed line, one pair at the
    # league-average line: short enough not to collide on a phone.
    note(f, t["kills"], top * 1.16, f"Observed: {t['kills']} kills", color=c, xanchor="right")
    note(f, t["kills"], top * 1.16, f"random order: {mean:.0f} (z {t['z_game']:.2f})", color=INK2,
         xanchor="right", yshift=-15)
    note(f, avg, top * 0.6, f"{lname} average", color=GREY, xanchor="left")
    note(f, avg, top * 0.6, f"kill rate: {avg:.0f}", color=GREY, xanchor="left", yshift=-15)
    f.update_layout(**base_layout(
        f"{t['season']} {t['team']} piled up kills by stopping more possessions, "
        "not by bunching its stops", "Kills in the season", "Share of random orderings (%)",
        height=420))
    f.update_layout(showlegend=False, bargap=0.05)
    f.update_yaxes(range=[0, top * 1.25])
    f.update_xaxes(range=[avg - 12, float(shown["kills"].max())])
    return f


def elapsed_min(period: int, secs_left: float, league: str) -> float:
    q = 720 if league == "nba" else 600
    if period <= 4:
        return ((period - 1) * q + (q - secs_left)) / 60
    return (4 * q + (period - 5) * 300 + (300 - secs_left)) / 60


def record_series(rg: pl.DataFrame, rec: dict) -> dict:
    """The record team's margin through the game and the streak's span."""
    team, league = rec["team"], rec["league"]
    rg = rg.filter(pl.col("abbr_ok")).sort("ord")
    xs, ys, m = [0.0], [0], 0
    for r in rg.iter_rows(named=True):
        if r["pts"]:
            t = elapsed_min(r["period"], r["end"], league)
            xs.append(t)
            ys.append(m)
            m += r["pts"] if r["offense"] == team else -r["pts"]
            xs.append(t)
            ys.append(m)
    end_t = elapsed_min(int(rg["period"].max()), 0.0, league)
    xs.append(end_t)
    ys.append(m)
    # The streak: the run of rec["length"] stops starting at its first possession.
    d = rg.filter(pl.col("defense") == team).with_columns(stop=(pl.col("pts") == 0))
    first = d.filter((pl.col("period") == rec["start_period"])
                     & (pl.col("start") == rec["start_clock"])).row(0, named=True)["ord"]
    seq = d.filter(pl.col("ord") >= first)
    run = seq.head(rec["length"])
    assert run["stop"].all() and (seq.height == run.height or not seq["stop"][rec["length"]])
    last = run.row(-1, named=True)
    nxt = rg.filter((pl.col("ord") > last["ord"]) & (pl.col("defense") == team)).head(1)

    def margin_before(o: int) -> int:
        b = rg.filter(pl.col("ord") < o)
        return int(b.filter(pl.col("offense") == team)["pts"].sum()
                   - b.filter(pl.col("offense") != team)["pts"].sum())

    after = margin_before(nxt.row(0, named=True)["ord"]) if nxt.height else m
    assert margin_before(first) == rec["margin_start"]
    return dict(xs=xs, ys=ys, final=m, end_t=end_t, before=rec["margin_start"], after=after,
                t0=elapsed_min(rec["start_period"], rec["start_clock"], league),
                t1=elapsed_min(rec["end_period"], rec["end_clock"], league),
                own_pts=int(rg.filter((pl.col("offense") == team) & (pl.col("ord") > first)
                                      & (pl.col("ord") < last["ord"]))["pts"].sum()))


def fig_record(rg: pl.DataFrame, records: pl.DataFrame) -> go.Figure:
    rec = records.filter((pl.col("league") == "nba") & (pl.col("rank") == 1)).row(0, named=True)
    s = record_series(rg, rec)
    team, opp = rec["team"], rec["opponent"]
    c = COLORS[rec["league"]]
    lo, hi = min(s["ys"]) - 7, max(s["ys"]) + 7
    f = go.Figure()
    f.add_trace(go.Scatter(
        x=[s["t0"], s["t1"], s["t1"], s["t0"], s["t0"]], y=[lo, lo, hi, hi, lo], fill="toself",
        fillcolor="rgba(42,120,214,0.14)", mode="lines", line=dict(width=0),
        name=f"{opp} scoreless: {rec['length']} straight possessions", hoverinfo="skip"))
    f.add_trace(go.Scatter(
        x=s["xs"], y=s["ys"], mode="lines", name=f"{team} margin", line=dict(color=c, width=2.5),
        hovertemplate=f"minute %{{x:.1f}}: {team} %{{y:+d}}<extra></extra>"))
    f.add_hline(y=0, line=dict(color="#b5b3ad", width=1))
    q = 12 if rec["league"] == "nba" else 10
    for k in range(1, int(s["end_t"] // q)):
        f.add_vline(x=k * q, line=dict(color=BAND, width=1, dash="dash"))
    # Labels sit below the line's low point, either side of the streak.
    note(f, s["t0"], lo + 2, f"Began: {s['before']:+d}", color=c, xanchor="right")
    note(f, s["t1"], lo + 2, f"Ended: {s['after']:+d}", color=c, xanchor="left")
    note(f, (s["t0"] + s["t1"]) / 2, hi, f"{opp} scoreless on {rec['length']} straight",
         color=c, xanchor="center", yanchor="top", yshift=-4)
    note(f, (s["t0"] + s["t1"]) / 2, hi, "possessions", color=c, xanchor="center", yanchor="top",
         yshift=-19)
    f.update_layout(**base_layout(
        f"{team}'s {rec['length']} straight stops turned a {abs(s['before'])}-point deficit "
        f"into a {s['after']}-point lead", "Minutes played", f"{team} margin (points)",
        height=420))
    f.update_layout(showlegend=False)
    f.update_xaxes(range=[0, s["end_t"]], tickvals=[k * q for k in range(int(s["end_t"] // q) + 1)])
    f.update_yaxes(range=[lo, hi])
    return f


def fig_leaders(lead: pl.DataFrame, ts: pl.DataFrame, summ: pl.DataFrame) -> go.Figure:
    lg = "nba"
    top = lead.filter((pl.col("ranked_by") == "kill_rate") & (pl.col("league") == lg)
                      & (pl.col("rank") <= 10)).sort("rank")
    all_lg = ts.filter(pl.col("league") == lg).with_columns(
        stop_rank=pl.col("stop_rate").rank(method="min", descending=True).cast(pl.Int32),
        exp_rate=100 * pl.col("exp_game") / pl.col("opp_poss"))
    top = top.join(all_lg.select("season", "team", "stop_rank", "exp_rate"),
                   on=["season", "team"], how="left")
    n = all_lg.height
    s = summ.filter(pl.col("league") == lg).row(0, named=True)
    avg = 100 * s["kills"] / float(all_lg["opp_poss"].sum())
    # Top row first: famplot and plotly list categories bottom-up, so reverse.
    rows = list(reversed(top.rows(named=True)))
    labels = [f"{r['season']} {r['team']} (stops {ordinal(r['stop_rank'])})" for r in rows]
    c = COLORS[lg]
    f = go.Figure()
    for r, lab in zip(rows, labels):
        f.add_trace(go.Scatter(x=[r["exp_rate"], r["kill_rate"]], y=[lab, lab], mode="lines",
                               line=dict(color=BAND, width=3), showlegend=False, hoverinfo="skip"))
    f.add_trace(go.Scatter(
        x=[r["exp_rate"] for r in rows], y=labels, mode="markers", name="Random order of its own stops",
        marker=dict(size=11, color="#a9c8ee"),
        hovertemplate="%{y}: %{x:.2f} per 100 in random order<extra></extra>"))
    f.add_trace(go.Scatter(
        x=[r["kill_rate"] for r in rows], y=labels, mode="markers", name="Observed",
        marker=dict(size=11, color=c),
        customdata=[[100 * r["stop_rate"], r["z_game"]] for r in rows],
        hovertemplate="%{y}: %{x:.2f} kills per 100, stops %{customdata[0]:.1f}%, "
                      "z %{customdata[1]:.2f}<extra></extra>"))
    # The league average sits far left of every dumbbell; drawing it as a
    # line left most of the plot empty, so it is a note at the left edge.
    note(f, 0, 1.0, f"← {LEAGUES[lg]} average: {avg:.2f} per 100, off this scale",
         color=GREY, xanchor="left", xref="paper", yref="paper", yanchor="top")
    worst = int(top["stop_rank"].max())
    f.update_layout(**base_layout(
        f"The {top.height} best NBA kill rates all come from top-{worst} stop rates "
        f"(of {n} team-seasons)", "Kills per 100 opponent possessions", "", height=470))
    xs = top["kill_rate"].to_list() + top["exp_rate"].to_list()
    f.update_xaxes(range=[min(xs) - 0.1, max(xs) + 0.1])
    f.update_layout(margin=dict(l=210, r=30, t=70, b=60))
    return f


# ---------------------------------------------------------------- diagram

def strip_diagram(ex: pl.DataFrame, width: int, split: int | None) -> famdiagram.Diagram:
    """Cells for one defense's opponent possessions, stops filled, kills
    bracketed in threes. split: cells per first row (None: one row)."""
    narrow = split is not None
    fs = 12.5 if narrow else 17
    stops = ex["stop"].to_list()
    pts = ex["pts"].to_list()
    per = ex["period"].to_list()
    n = len(stops)
    rows = [list(range(n))] if not narrow else [list(range(split)), list(range(split, n))]
    gap = 5 if narrow else 6
    left = 12 if narrow else 20
    per_row = max(len(r) for r in rows)
    cw = (width - 2 * left - gap * (per_row - 1)) / per_row
    ch = cw * (0.95 if narrow else 0.8)
    row_h = ch + (fs * 6.6)
    top = fs * 4.6
    a = ex.row(0, named=True)
    height = top + row_h * len(rows) + fs * 2.6
    d = famdiagram.Diagram(width, height, "What counts as a kill")
    title = (f"{a['team']} defense against {a['opponent']}, {long_date(a['game_date'])}")
    d.text(left, fs * 1.4, title, size=fs * 1.15, weight=600)
    d.text(left, fs * 2.8, f"{n} {a['opponent']} possessions in a row", size=fs, fill="ink2")
    # legend
    lx = width - left
    if not narrow:
        d.rect(lx - 300, fs * 1.9, fs, fs, fill="nba", rx=3)
        d.text(lx - 300 + fs * 1.4, fs * 2.8, "stop", size=fs, fill="ink2")
        d.rect(lx - 190, fs * 1.9, fs, fs, fill="surface2", stroke="ink3", rx=3)
        d.text(lx - 190 + fs * 1.4, fs * 2.8, "score (points)", size=fs, fill="ink2")
    pos = {}
    for ri, r in enumerate(rows):
        y = top + ri * row_h + fs * 1.6
        for j, i in enumerate(r):
            pos[i] = (left + j * (cw + gap), y)
    for i in range(n):
        x, y = pos[i]
        if stops[i]:
            d.rect(x, y, cw, ch, fill="nba", rx=4)
        else:
            d.rect(x, y, cw, ch, fill="surface2", stroke="ink3", rx=4)
            d.text(x + cw / 2, y + ch / 2 + fs * 0.38, str(pts[i]), size=fs, fill="ink",
                   anchor="middle", weight=600)
    # quarter labels and the break
    for i in range(n):
        if i == 0 or per[i] != per[i - 1] or (narrow and i == split):
            x, y = pos[i]
            d.text(x, y - fs * 0.5, f"Q{per[i]}", size=fs, fill="ink3", weight=600)
        if i > 0 and per[i] != per[i - 1] and pos[i][1] == pos[i - 1][1]:
            x, y = pos[i]
            bx = x - gap / 2
            d.line(bx, y - fs * 1.4, bx, y + ch + fs * 0.4, stroke="ink2", sw=2, dash="4 3")
    # kill brackets and run totals
    for i0, L, _ in run_spans(stops, per):
        k = L // 3
        for j in range(k):
            a0, a1 = i0 + 3 * j, i0 + 3 * j + 2
            x0, y0 = pos[a0]
            x1, _ = pos[a1]
            by = y0 + ch + fs * 0.7
            d.path(f"M{x0 + 2:.1f},{by - 5:.1f} V{by:.1f} H{x1 + cw - 2:.1f} V{by - 5:.1f}",
                   stroke="nba", sw=2)
            d.text((x0 + x1 + cw) / 2, by + fs * 1.2, f"kill {j + 1}" if k > 1 else "kill",
                   size=fs, fill="nba", anchor="middle", weight=600)
        if L % 3:
            x0, y0 = pos[i0 + 3 * k]
            x1, _ = pos[i0 + L - 1]
            d.text((x0 + x1 + cw) / 2, y0 + ch + fs * 1.9, "no kill", size=fs, fill="ink3",
                   anchor="middle")
        xs, ys = pos[i0]
        a_cnt = per[i0:i0 + L].count(per[i0])
        crosses = a_cnt < L
        line = f"{L} straight stops = {k} kill{'s' if k != 1 else ''}"
        d.text(xs, ys + ch + fs * 3.6, line, size=fs, fill="ink", weight=600)
        if crosses:
            apart = a_cnt // 3 + (L - a_cnt) // 3
            d.text(xs, ys + ch + fs * 4.9,
                   f"across the break ({a_cnt} + {L - a_cnt}; {apart} if it reset)",
                   size=fs, fill="ink2")
        elif L % 3:
            d.text(xs, ys + ch + fs * 4.9, f"the last {L % 3} start nothing", size=fs, fill="ink2")
    if narrow:
        y = height - fs * 0.9
        d.rect(left, y - fs * 0.85, fs, fs, fill="nba", rx=3)
        d.text(left + fs * 1.4, y, "stop", size=fs, fill="ink2")
        d.rect(left + fs * 5, y - fs * 0.85, fs, fs, fill="surface2", stroke="ink3", rx=3)
        d.text(left + fs * 6.4, y, "score (points)", size=fs, fill="ink2")
    return d


def run_spans(stops: list[int], per: list[int]) -> list[tuple[int, int, list[int]]]:
    out, i = [], 0
    while i < len(stops):
        if stops[i]:
            j = i
            while j < len(stops) and stops[j]:
                j += 1
            out.append((i, j - i, per[i:j]))
            i = j
        else:
            i += 1
    return out


def diagrams() -> None:
    ex = pl.read_csv(OUT / "example_strip.csv").sort("seq_index")
    stops = ex["stop"].to_list()
    # Narrow layout: break the row after the score that ends the first run.
    first = run_spans(stops, ex["period"].to_list())[0]
    split = first[0] + first[1] + 1
    famdiagram.save(FIG, "dg_kill_rules", strip_diagram(ex, 900, None),
                    strip_diagram(ex, 360, split))
    print("wrote dg_kill_rules")


def main() -> None:
    FIG.mkdir(exist_ok=True)
    ts = pl.read_csv(OUT / "team_seasons.csv")
    ls = pl.read_csv(OUT / "league_seasons.csv")
    summ = pl.read_csv(OUT / "summary.csv")
    lead = pl.read_csv(OUT / "leaders.csv")
    pe = pl.read_csv(OUT / "perm_example.csv")
    rg = pl.read_csv(OUT / "record_game.csv", schema_overrides={"gameId": pl.Utf8})
    records = pl.read_csv(OUT / "records.csv", schema_overrides={"gameId": pl.Utf8})
    for name, fig in [("fig1_kill_vs_stop_py", fig_scatter(ts, summ)), ("fig2_streak_z_py", fig_z(ls)),
                      ("fig3_kill_rate_py", fig_rate(ls)),
                      ("fig4_perm_baseline_py", fig_perm(pe, ts, ls)),
                      ("fig5_record_margin_py", fig_record(rg, records)),
                      ("fig6_leaders_py", fig_leaders(lead, ts, summ))]:
        fig.write_html(FIG / f"{name}.html", include_plotlyjs="cdn", full_html=True)
        fig.write_image(FIG / f"{name}.png", width=900, height=fig.layout.height or 440, scale=2)
        print("wrote", name)
    diagrams()


if __name__ == "__main__":
    main()
