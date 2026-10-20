"""The live builds against the archive, on the four seasons both cover (NBA
2023-24 and 2024-25, WNBA 2024 and 2025): the check that lets NBA 2025-26
and WNBA 2026 come from the live builds at all.

For each overlap season, both sources go through the same points assignment
(python/lib.py) and kill count, with and without the live-build corrections,
and are compared:
  offense_agrees    share of possessions present in both (same game, period,
                    start, end) whose offense agrees
  kills_diff        live kills / archive kills - 1, league total
  rate_corr         correlation of team-season kill rates
  rate_mean_diff    mean of live minus archive team-season kill rate (per 100)
  rate_max_abs_diff the largest absolute team difference
  rate_sd           spread of archive kill rates across teams, for scale

Writes output/source_check.csv. --check recomputes it and fails on any
difference, or if a corrected season has rate_corr under 0.99, an absolute
rate_mean_diff over 0.05, an absolute kills_diff over 2%, or offense_agrees
under 0.998. This check is Python only: it validates an input, and both
languages then read the same corrected possessions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

POSS = lib.ROOT / "data" / "possessions"
OUT = lib.ROOT / "output" / "source_check.csv"
EV_COLS = ["gameId", "seq", "period", "secs_left", "actionType", "location",
           "score_h", "score_a", "home_id", "away_id", "isFieldGoal", "teamId"]


def team_seasons(p: pl.DataFrame) -> pl.DataFrame:
    p = p.filter("abbr_ok").with_columns(stop=(pl.col("pts") == 0).cast(pl.Int32)).sort("gameId", "dfn", "ord")
    st = lib.streak_table(p)
    k = st.group_by("dfn").agg(kills=(pl.col("length") // 3).sum())
    n = p.group_by("dfn").agg(n=pl.len())
    return n.join(k, on="dfn", how="left").with_columns(
        pl.col("kills").fill_null(0), rate=100 * pl.col("kills").fill_null(0) / pl.col("n"))


def uncorrected(raw: pl.DataFrame, fin: pl.DataFrame) -> pl.DataFrame:
    """A live build as stored, in possessions()' schema, for comparison."""
    ok = fin.filter(pl.col("status") == "ok").select("gameId", "home_id", "away_id")
    p = (raw.select(gameId=pl.col("game_id").cast(pl.Utf8).str.zfill(10),
                    period=pl.col("PERIOD").cast(pl.Int32), start="start_secs", end="end_secs",
                    off=pl.col("offense_team_id").cast(pl.Int64))
            .join(ok, on="gameId", how="inner"))
    p = p.with_columns(abbr_ok=(pl.col("off") == pl.col("home_id")) | (pl.col("off") == pl.col("away_id")),
                       dfn=pl.when(pl.col("off") == pl.col("home_id")).then(pl.col("away_id"))
                             .otherwise(pl.col("home_id")))
    p = p.sort(["gameId", "period", "start", "end", "off"], descending=[False, False, True, True, False])
    p = p.with_columns(ord=pl.int_range(pl.len()).over("gameId").cast(pl.Int32))
    return p.select("gameId", "period", "start", "end", "off", "dfn", "ord", "abbr_ok")


def compute() -> pl.DataFrame:
    rows = []
    for (league, year), name in lib.OVERLAP.items():
        fin = lib.pbp_history.load_finals(league, [year])
        ev = pl.read_parquet(lib.pbp_history.events_path(league, year), columns=EV_COLS)
        arch = pl.read_parquet(POSS / f"{league}_{year}.parquet")
        a = team_seasons(arch)
        raw = lib.live_raw(name)
        for corrected in (False, True):
            live = lib.live_possessions(raw, fin, ev) if corrected else uncorrected(raw, fin)
            sc = lib.scoring_events(ev.join(live.select("gameId").unique(), on="gameId", how="semi"))
            live, _ = lib.attribute_points(live, sc)
            l = team_seasons(live)
            c = a.join(l, on="dfn", suffix="_l")
            d = c["rate_l"] - c["rate"]
            m = live.join(arch.select("gameId", "period", "start", "end", off_a="off"),
                          on=["gameId", "period", "start", "end"], how="inner")
            rows.append({"league": league, "year": year,
                         "season": lib.pbp_history.season_label(league, year),
                         "corrected": corrected, "archive_possessions": arch.height,
                         "live_possessions": live.height,
                         "offense_agrees": float((m["off"] == m["off_a"]).mean()),
                         "kills_archive": int(a["kills"].sum()), "kills_live": int(l["kills"].sum()),
                         "kills_diff": float(l["kills"].sum() / a["kills"].sum() - 1),
                         "rate_corr": float(c.select(pl.corr("rate", "rate_l")).item()),
                         "rate_mean_diff": float(d.mean()), "rate_max_abs_diff": float(d.abs().max()),
                         "rate_sd": float(c["rate"].std())})
    return pl.DataFrame(rows).with_columns(pl.col(pl.Float64).round(12))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    df = compute()
    c = df.filter("corrected")
    bad = c.filter((pl.col("rate_corr") < 0.99) | (pl.col("rate_mean_diff").abs() > 0.05)
                   | (pl.col("kills_diff").abs() > 0.02) | (pl.col("offense_agrees") < 0.998))
    fails = [f"live builds drift from the archive: {bad.select('league', 'year').rows()}"] if bad.height else []
    if args.check:
        if not lib.frames_match(df, pl.read_csv(OUT, schema_overrides=df.schema)):
            fails.append("source_check.csv differs from a fresh build")
        for f in fails:
            print("FAIL", f)
        print("SOURCES", "FAILED" if fails else
              f"PASSED: corrected live builds match the archive on {c.height} seasons "
              f"(kill-rate correlation at least {c['rate_corr'].min():.4f})")
        return 1 if fails else 0
    df.write_csv(OUT)
    with pl.Config(tbl_width_chars=220):
        print(df.select("league", "year", "corrected", "offense_agrees", "kills_diff", "rate_corr",
                        "rate_mean_diff", "rate_max_abs_diff", "rate_sd"))
    for f in fails:
        print("WARN", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
