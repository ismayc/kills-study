"""Kills, stop streaks, and the streakiness test. Definitions in python/lib.py.

For every defense and game, the opponent's possessions in game order are a
0/1 stop sequence. Per team-season:
  opp_poss, stops, stop_rate, kills, kill_rate (kills per 100 opponent
  possessions), share_in_kill (3 * kills / opp_poss), pts_allowed_per100,
  exp_season and var_season (expected kills and variance if every possession
  were a stop with the team-season's stop rate, independently),
  exp_game and var_game (each game's own stops in a random order, which holds
  every game's stop count fixed and absorbs opponent strength and
  blowouts), z_season, z_game, and kill_rate_z
  (kill_rate as a z-score within the league-season).

Writes (committed):
  output/team_seasons.csv    one row per defense team-season
  output/league_seasons.csv  per league-season: sums of observed and expected
                             kills, the excess, and its z under both baselines
  output/records.csv         the 25 longest stop streaks in each league
  output/season_records.csv  the longest streak in each league-season
  output/leaders.csv         the 15 best kill rates per league, raw and as a
                             within-season z
  output/summary.csv         per league: kills against both baselines pooled
                             over every season (excess and z), the share of
                             team-seasons with |z_game| > 1.96, and the
                             correlation and R^2 of kill_rate on stop_rate
                             across team-seasons
--check recomputes everything from data/possessions/ and fails on any
difference.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

POSS = lib.ROOT / "data" / "possessions"
OUT = lib.ROOT / "output"
NAMES = ["team_seasons", "league_seasons", "records", "season_records", "leaders", "summary"]


def expected(n_by_game: list[int], p_by_game: list[float]) -> tuple[float, float]:
    e = v = 0.0
    for n, p in zip(n_by_game, p_by_game):
        m, s2 = lib.expected_kills(int(n), round(float(p), 12))
        e += m
        v += s2
    return e, v


def season(league: str, year: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(team-season rows, streak rows) for one league-season."""
    p = pl.read_parquet(POSS / f"{league}_{year}.parquet").filter(pl.col("abbr_ok"))
    # Running score from possession points, in game order: each team's points
    # before each possession, then the margin from the defense's side. It
    # omits the rare unassigned free throw (output/validation.csv).
    p = p.sort("gameId", "ord").with_columns(t1=pl.col("off").min().over("gameId"))
    p = p.with_columns(p1=pl.when(pl.col("off") == pl.col("t1")).then(pl.col("pts")).otherwise(0),
                       p2=pl.when(pl.col("off") != pl.col("t1")).then(pl.col("pts")).otherwise(0))
    p = p.with_columns(b1=pl.col("p1").cum_sum().over("gameId") - pl.col("p1"),
                       b2=pl.col("p2").cum_sum().over("gameId") - pl.col("p2"))
    p = p.with_columns(
        margin_before=pl.when(pl.col("dfn") == pl.col("t1")).then(pl.col("b1") - pl.col("b2"))
                        .otherwise(pl.col("b2") - pl.col("b1")),
        stop=(pl.col("pts") == 0).cast(pl.Int32)).sort("gameId", "dfn", "ord")
    st = lib.streak_table(p)
    tg = (p.group_by("gameId", "dfn")
           .agg(n=pl.len(), stops=pl.col("stop").sum(), pts=pl.col("pts").sum()))
    kg = st.group_by("gameId", "dfn").agg(kills=(pl.col("length") // 3).sum())
    tg = tg.join(kg, on=["gameId", "dfn"], how="left").with_columns(pl.col("kills").fill_null(0))
    rows = []
    for (dfn,), g in tg.group_by("dfn", maintain_order=True):
        g = g.sort("gameId")
        n, s = int(g["n"].sum()), int(g["stops"].sum())
        ps = s / n
        es, vs = expected(g["n"].to_list(), [ps] * g.height)
        eg = vg = 0.0
        for gn, gs in zip(g["n"].to_list(), g["stops"].to_list()):
            m, v2 = lib.expected_kills_perm(int(gn), int(gs))
            eg += m
            vg += v2
        k = int(g["kills"].sum())
        rows.append({"league": league, "year": year,
                     "season": lib.pbp_history.season_label(league, year), "team_id": dfn,
                     "games": g.height, "opp_poss": n, "stops": s, "stop_rate": ps,
                     "kills": k, "kill_rate": lib.per100(k, n), "share_in_kill": 3 * k / n,
                     "pts_allowed_per100": lib.per100(int(g["pts"].sum()), n),
                     "exp_season": es, "var_season": vs, "exp_game": eg, "var_game": vg,
                     "z_season": (k - es) / math.sqrt(vs), "z_game": (k - eg) / math.sqrt(vg)})
    first = p.select("gameId", "dfn", "ord", start_period="period", start_clock="start",
                     margin_start="margin_before")
    last = p.select("gameId", "dfn", "ord", end_period="period", end_clock="end",
                    margin_end=pl.col("margin_before"))  # the streak's last stop adds nothing
    st = (st.join(first, left_on=["gameId", "dfn", "first_ord"], right_on=["gameId", "dfn", "ord"])
            .join(last, left_on=["gameId", "dfn", "last_ord"], right_on=["gameId", "dfn", "ord"]))
    # The defense may score during the streak; the margin after the last stop
    # is the margin before the next opponent possession, or the final margin.
    return pl.DataFrame(rows), st.with_columns(league=pl.lit(league), year=pl.lit(year))


def team_abbr(meta: pl.DataFrame) -> pl.DataFrame:
    """Most frequent LeagueGameLog abbreviation per league-season and team."""
    t = pl.concat([meta.select("league", "year", team_id="home_id", team="abbr_h"),
                   meta.select("league", "year", team_id="away_id", team="abbr_a")])
    return (t.group_by("league", "year", "team_id", "team").len()
             .sort(["league", "year", "team_id", "len", "team"],
                   descending=[False, False, False, True, False])
             .group_by("league", "year", "team_id", maintain_order=True).first()
             .drop("len"))


def compute() -> dict[str, pl.DataFrame]:
    tss, sts, metas = [], [], []
    for league, years in lib.YEARS.items():
        for y in years:
            t, s = season(league, y)
            tss.append(t)
            sts.append(s)
        f = lib.pbp_history.load_finals(league, list(years)).filter(pl.col("status") == "ok")
        metas.append(f.select("gameId", "year", "game_date", "home_id", "away_id", "abbr_h",
                              "abbr_a").with_columns(league=pl.lit(league)))
    meta = pl.concat(metas)
    ts = (pl.concat(tss).join(team_abbr(meta), on=["league", "year", "team_id"], how="left")
            .sort("league", "year", "team_id"))
    ts = ts.with_columns(
        kill_rate_z=(pl.col("kill_rate") - pl.col("kill_rate").mean().over("league", "year"))
        / pl.col("kill_rate").std().over("league", "year"))
    st = pl.concat(sts).join(meta.drop("league", "year"), on="gameId").with_columns(
        team=pl.when(pl.col("dfn") == pl.col("home_id")).then(pl.col("abbr_h")).otherwise(pl.col("abbr_a")),
        opponent=pl.when(pl.col("dfn") == pl.col("home_id")).then(pl.col("abbr_a")).otherwise(pl.col("abbr_h")),
        season=pl.when(pl.col("league") == "nba")
                 .then(pl.format("{}-{}", pl.col("year"), ((pl.col("year") + 1) % 100).cast(pl.Utf8).str.zfill(2)))
                 .otherwise(pl.col("year").cast(pl.Utf8)))
    st = st.select("league", "year", "season", "gameId", "game_date", "team", "opponent", "length",
                   "start_period", "start_clock", "margin_start", "end_period", "end_clock")
    order, desc = ["length", "game_date", "gameId", "team"], [True, False, False, False]
    records = pl.concat([st.filter(pl.col("league") == lg).sort(order, descending=desc).head(25)
                         .with_columns(rank=pl.int_range(1, 26)) for lg in lib.YEARS])
    season_records = (st.sort(order, descending=desc)
                        .group_by("league", "year", maintain_order=True).first()
                        .sort("league", "year"))
    ls = (ts.group_by("league", "year", "season")
            .agg(teams=pl.len(), opp_poss=pl.col("opp_poss").sum(), kills=pl.col("kills").sum(),
                 exp_season=pl.col("exp_season").sum(), var_season=pl.col("var_season").sum(),
                 exp_game=pl.col("exp_game").sum(), var_game=pl.col("var_game").sum())
            .with_columns(kill_rate=100 * pl.col("kills") / pl.col("opp_poss"),
                          excess_season=pl.col("kills") - pl.col("exp_season"),
                          excess_game=pl.col("kills") - pl.col("exp_game"))
            .with_columns(z_season=pl.col("excess_season") / pl.col("var_season").sqrt(),
                          z_game=pl.col("excess_game") / pl.col("var_game").sqrt())
            .sort("league", "year"))
    lead = []
    for lg in lib.YEARS:
        x = ts.filter(pl.col("league") == lg)
        for by in ("kill_rate", "kill_rate_z"):
            lead.append(x.sort([by, "year", "team_id"], descending=[True, False, False]).head(15)
                        .select(pl.lit(by).alias("ranked_by"), pl.int_range(1, 16).alias("rank"),
                                "league", "season", "team", "kill_rate", "kill_rate_z", "stop_rate",
                                "pts_allowed_per100", "z_game"))
    summ = []
    for lg in lib.YEARS:
        x = ts.filter(pl.col("league") == lg)
        k = float(x["kills"].sum())
        r = float(np.corrcoef(x["stop_rate"].to_numpy(), x["kill_rate"].to_numpy())[0, 1])
        summ.append({"league": lg, "team_seasons": x.height, "kills": int(k),
                     "excess_season": k - float(x["exp_season"].sum()),
                     "z_season": (k - float(x["exp_season"].sum())) / math.sqrt(float(x["var_season"].sum())),
                     "excess_game": k - float(x["exp_game"].sum()),
                     "z_game": (k - float(x["exp_game"].sum())) / math.sqrt(float(x["var_game"].sum())),
                     "share_abs_z_over_1_96": float((x["z_game"].abs() > 1.959963984540054).mean()),
                     "corr_stop_kill": r, "r2_stop_kill": r * r})
    r12 = lambda df: df.with_columns(pl.col(pl.Float64).round(12))  # noqa: E731
    return {"team_seasons": r12(ts), "league_seasons": r12(ls), "records": r12(records),
            "season_records": r12(season_records), "leaders": r12(pl.concat(lead)),
            "summary": r12(pl.DataFrame(summ))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    res = compute()
    if args.check:
        fails = [f"{n}.csv differs from a fresh build" for n, df in res.items()
                 if not lib.frames_match(df, pl.read_csv(OUT / f"{n}.csv", schema_overrides=df.schema))]
        for f in fails:
            print("FAIL", f)
        print("KILLS", "FAILED" if fails else f"PASSED: {res['team_seasons'].height:,} team-seasons")
        return 1 if fails else 0
    for n, df in res.items():
        df.write_csv(OUT / f"{n}.csv")
    with pl.Config(tbl_rows=60, tbl_width_chars=220):
        print(res["summary"])
        print(res["records"].select("league", "rank", "season", "game_date", "team", "opponent",
                                    "length", "start_period", "start_clock", "end_period",
                                    "end_clock", "margin_start").head(12))
        print(res["leaders"].filter(pl.col("ranked_by") == "kill_rate").head(8))
    return 0


if __name__ == "__main__":
    sys.exit(main())
