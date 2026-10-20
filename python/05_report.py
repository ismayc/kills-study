"""Write the README's results section from the output tables, so no number in
it is typed by hand. Replaces the text between <!-- gen:results --> and
<!-- /gen:results -->. --check fails if the README is out of date.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
README = ROOT / "README.md"
START, END = "<!-- gen:results -->", "<!-- /gen:results -->"
LEAGUE = {"nba": "NBA", "wnba": "WNBA"}
Q = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}


def clock(period: int, secs: float, league: str, year: int) -> str:
    s = int(secs)
    name = Q.get(period, f"OT{period - 4}")
    return f"{s // 60}:{s % 60:02d} {name}"


def results() -> str:
    va = pl.read_csv(OUT / "validation.csv")
    su = pl.read_csv(OUT / "summary.csv")
    ls = pl.read_csv(OUT / "league_seasons.csv")
    rec = pl.read_csv(OUT / "records.csv")
    srec = pl.read_csv(OUT / "season_records.csv")
    lead = pl.read_csv(OUT / "leaders.csv")
    v = va.group_by("league").agg(pl.col("games", "games_ok", "possessions").sum(),
                                  pl.col("points_captured").min().alias("worst"))
    vv = {r["league"]: r for r in v.iter_rows(named=True)}
    s = {r["league"]: r for r in su.iter_rows(named=True)}
    lines = [
        f"Coverage: {vv['nba']['games']:,} NBA games (2000-01 to 2024-25) and "
        f"{vv['wnba']['games']:,} WNBA games (2009 to 2025), "
        f"{vv['nba']['possessions'] + vv['wnba']['possessions']:,} possessions, every "
        "archive game whose score passes the shared layer's checks "
        f"({vv['nba']['games_ok'] - vv['nba']['games'] + vv['wnba']['games_ok'] - vv['wnba']['games']} "
        "such games are missing from the possession archive). Possession points capture at least "
        f"{min(vv['nba']['worst'], vv['wnba']['worst']):.2%} of every season's points; the rest are "
        "free throws that belong to no possession (technicals, a period's first second). "
        "Every table is computed in Python and again in R, and the two agree on every cell.",
        "",
        "### 1. What a kill measures beyond the stop rate",
        "",
        "Across team-seasons, the correlation between stop rate and kill rate is "
        f"{s['nba']['corr_stop_kill']:.3f} in the NBA and {s['wnba']['corr_stop_kill']:.3f} in "
        f"the WNBA: stop rate alone explains {s['nba']['r2_stop_kill']:.0%} and "
        f"{s['wnba']['r2_stop_kill']:.0%} of the variation in kill rate.",
        "",
        "The sharper test holds each game's stops fixed and asks whether they cluster: "
        "against every ordering of a game's own stops being equally likely, how many kills "
        "should a team have had? (This baseline already absorbs opponent strength, pace, and "
        "blowouts, because it keeps each game's stop count.)",
        "",
        "| League | Team-seasons | Kills | Excess over random order | z | Team-seasons with abs(z) > 1.96 |",
        "|---|---|---|---|---|---|",
    ]
    for lg in LEAGUE:
        r = s[lg]
        lines.append(f"| {LEAGUE[lg]} | {r['team_seasons']} | {r['kills']:,} | "
                     f"{r['excess_game']:+,.0f} ({r['excess_game'] / r['kills']:+.2%}) | "
                     f"{r['z_game']:+.2f} | {r['share_abs_z_over_1_96']:.1%} |")
    nseas = ls.filter(pl.col("league") == "nba")
    neg = nseas.filter(pl.col("z_game") < 0).height
    lines += [
        "",
        f"About 5% of team-seasons would pass 1.96 by chance alone; "
        f"{s['nba']['share_abs_z_over_1_96']:.1%} and {s['wnba']['share_abs_z_over_1_96']:.1%} "
        "do. So no team's defense strings its stops together more than its stop rate "
        f"implies. The WNBA's pooled count sits at chance (z {s['wnba']['z_game']:+.2f}). The "
        f"NBA's is slightly below it (z {s['nba']['z_game']:+.2f}; {neg} of {nseas.height} "
        "seasons below zero): stops alternate with scores a little more often than random "
        "order would give, by a fraction of a percent. The cause is not tested here.",
        "",
        "![Kill rate against stop rate](figures/fig1_kill_vs_stop_py.png)",
        "",
        "![Observed against random-order kills, by season](figures/fig2_streak_z_py.png)",
        "",
        "### 2. Best kill rates",
        "",
        "Kills per 100 opponent possessions; z is the same rate against that league-season's "
        "teams, and the last column is the team-season's own streakiness z (near zero means "
        "the kills came from the stop rate):",
        "",
    ]
    for lg in LEAGUE:
        t = lead.filter((pl.col("league") == lg) & (pl.col("ranked_by") == "kill_rate")).sort("rank").head(10)
        lines += [f"**{LEAGUE[lg]}**", "",
                  "| Rank | Season | Team | Kills per 100 | z in season | Stop rate | Streakiness z |",
                  "|---|---|---|---|---|---|---|"]
        for r in t.iter_rows(named=True):
            lines.append(f"| {r['rank']} | {r['season']} | {r['team']} | {r['kill_rate']:.2f} | "
                         f"{r['kill_rate_z']:.2f} | {r['stop_rate']:.1%} | {r['z_game']:+.2f} |")
        lines.append("")
    lines += ["### 3. The stop-streak record book", "",
              "Longest runs of opponent possessions without a point (a streak carries across "
              "quarters and ends at the final buzzer); the margin is the defense's when the "
              "streak began:", ""]
    for lg in LEAGUE:
        t = rec.filter(pl.col("league") == lg).sort("rank").head(10)
        lines += [f"**{LEAGUE[lg]}**", "",
                  "| Rank | Date | Defense | Opponent | Stops | From | To | Margin at start |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in t.iter_rows(named=True):
            lines.append(f"| {r['rank']} | {r['game_date']} | {r['team']} | {r['opponent']} | "
                         f"{r['length']} | {clock(r['start_period'], r['start_clock'], lg, r['year'])} | "
                         f"{clock(r['end_period'], r['end_clock'], lg, r['year'])} | {r['margin_start']:+d} |")
        lines.append("")
    lines.append("The longest streak of every season: `output/season_records.csv`; the top 25 per "
                 "league: `output/records.csv`.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = README.read_text()
    a, b = text.index(START) + len(START), text.index(END)
    new = text[:a] + "\n" + results() + "\n" + text[b:]
    if args.check:
        ok = new == text
        print("REPORT", "PASSED: README results match the outputs" if ok else
              "FAILED: README results are stale; run python/05_report.py")
        return 0 if ok else 1
    README.write_text(new)
    print("README results written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
