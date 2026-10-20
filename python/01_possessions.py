"""Possessions with points, for every archive season (NBA 2000-01 to 2024-25,
WNBA 2009 to 2025) and every game whose score passes the shared layer's
checks. Definitions in python/lib.py.

Writes (local, gitignored):
  data/raw_possessions/<league>_<year>.parquet  the archive's possession rows
                                                as read (R reads these)
  data/possessions/<league>_<year>.parquet      typed possessions with pts
Writes (committed): output/validation.csv, one row per league-season:
  games, possessions, abbr_unmatched, points_captured (share of all scored
  points assigned to a possession), team_games_exact (share of team-games
  whose possession points equal their total), unassigned (scoring events in
  no possession).
--check rebuilds in memory and fails if any season leaves an abbreviation
unmatched, captures under 99.5% of points, or differs from validation.csv.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

RAW = lib.ROOT / "data" / "raw_possessions"
POSS = lib.ROOT / "data" / "possessions"
VALID = lib.ROOT / "output" / "validation.csv"
EV_COLS = ["gameId", "seq", "period", "secs_left", "actionType", "location",
           "score_h", "score_a", "home_id", "away_id"]


def season(league: str, year: int, write: bool) -> dict:
    raw = lib.archive_possessions(league, year)
    fin = lib.pbp_history.load_finals(league, [year])
    poss = lib.possessions(raw, fin)
    ok = fin.filter(pl.col("status") == "ok").select("gameId")
    ev = pl.read_parquet(lib.pbp_history.events_path(league, year), columns=EV_COLS).join(
        poss.select("gameId").unique(), on="gameId", how="semi")
    sc = lib.scoring_events(ev)
    out, unassigned = lib.attribute_points(poss, sc)
    tot = sc.group_by("gameId", "team").agg(all=pl.col("pts").sum())
    got = out.group_by("gameId", team="off").agg(pts=pl.col("pts").sum())
    cmp = tot.join(got, on=["gameId", "team"], how="left").with_columns(pl.col("pts").fill_null(0))
    if write:
        RAW.mkdir(parents=True, exist_ok=True)
        POSS.mkdir(parents=True, exist_ok=True)
        raw.write_parquet(RAW / f"{league}_{year}.parquet")
        out.write_parquet(POSS / f"{league}_{year}.parquet")
    return {"league": league, "year": year,
            "season": lib.pbp_history.season_label(league, year),
            "games_ok": ok.height, "games": poss["gameId"].n_unique(), "possessions": poss.height,
            "abbr_unmatched": int((~poss["abbr_ok"]).sum()),
            "points_captured": round(float(cmp["pts"].sum() / cmp["all"].sum()), 12),
            "team_games_exact": round(float((cmp["pts"] == cmp["all"]).mean()), 12),
            "unassigned": unassigned.height}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = [season(lg, y, write=not args.check) for lg, ys in lib.YEARS.items() for y in ys]
    va = pl.DataFrame(rows)
    fails = []
    bad = va.filter(pl.col("abbr_unmatched") > 0)
    if bad.height:
        fails.append(f"unmatched abbreviations: {bad.select('league', 'year').rows()}")
    low = va.filter(pl.col("points_captured") < 0.995)
    if low.height:
        fails.append(f"points captured under 99.5%: {low.select('league', 'year').rows()}")
    if args.check:
        if not lib.frames_match(va, pl.read_csv(VALID, schema_overrides=va.schema)):
            fails.append("validation.csv differs from a fresh build")
        for f in fails:
            print("FAIL", f)
        print("POSSESSIONS", "FAILED" if fails else
              f"PASSED: {va['games'].sum():,} games, {va['possessions'].sum():,} possessions, "
              f"{va['points_captured'].min():.4%} of points captured in the worst season")
        return 1 if fails else 0
    va.write_csv(VALID)
    with pl.Config(tbl_rows=60):
        print(va)
    for f in fails:
        print("WARN", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
