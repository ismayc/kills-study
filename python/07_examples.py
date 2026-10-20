"""Small tables behind the story's explainer visuals.

Writes (committed):
  output/example_strip.csv   one defense's opponent possessions over a short
                             stretch of one game, the rows of the "what counts
                             as a kill" diagram. The stretch is chosen by rule
                             from NBA 2024-25, the newest archive season: a
                             defense-game holding a run of exactly six stops
                             that crosses a quarter break (and so makes more
                             kills than its two halves would apart) and a run
                             of exactly five; the smallest such stretch, then
                             the earliest gameId, then the lower team id. The
                             stretch runs from the score before the first run
                             to the score after the last. Raw rows of one game.
  output/record_game.csv     every possession of the NBA's top record-book
                             game (output/records.csv rank 1), for its score
                             margin over time. Raw rows of one game.
  output/perm_example.csv    the exact distribution of a team-season's kills
                             when each game's own stops fall in a random order
                             (lib.season_pmf_perm), for the NBA's top kill rate
                             (output/leaders.csv), kills from 100 below to 100
                             above the observed count. A computed table:
                             R/kills.R writes perm_example_r.csv and
                             python/03_reconcile.py compares them.

--check rebuilds all three and fails on any difference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

POSS = lib.ROOT / "data" / "possessions"
OUT = lib.ROOT / "output"
STRIP_SEASON = ("nba", 2024)
WINDOW = 100  # perm_example: kills from observed - WINDOW to observed + WINDOW


def stops_frame(league: str, year: int) -> pl.DataFrame:
    p = pl.read_parquet(POSS / f"{league}_{year}.parquet").filter(pl.col("abbr_ok"))
    return p.with_columns(stop=(pl.col("pts") == 0).cast(pl.Int32)).sort("gameId", "dfn", "ord")


def abbrs(league: str, year: int) -> pl.DataFrame:
    f = lib.pbp_history.load_finals(league, [year]).filter(pl.col("status") == "ok")
    return f.select("gameId", "game_date", "home_id", "away_id", "abbr_h", "abbr_a")


def run_list(stops: list[int], periods: list[int]) -> list[tuple[int, int, list[int]]]:
    """(first index, length, periods spanned) for each run of stops."""
    out, i = [], 0
    while i < len(stops):
        if stops[i]:
            j = i
            while j < len(stops) and stops[j]:
                j += 1
            out.append((i, j - i, periods[i:j]))
            i = j
        else:
            i += 1
    return out


def example_strip() -> pl.DataFrame:
    league, year = STRIP_SEASON
    p = stops_frame(league, year)
    best = None
    for (g, d), x in p.group_by(["gameId", "dfn"], maintain_order=True):
        rl = run_list(x["stop"].to_list(), x["period"].to_list())
        sixes = []
        for i, L, per in rl:
            if L == 6 and len(set(per)) > 1:
                a = per.count(per[0])
                if L // 3 > a // 3 + (L - a) // 3:
                    sixes.append((i, L))
        fives = [(i, L) for i, L, _ in rl if L == 5]
        for i6, _ in sixes:
            for i5, _ in fives:
                lo, hi = min(i6, i5), max(i6 + 6, i5 + 5)
                key = (hi - lo, g, d)
                if best is None or key < best[0]:
                    best = (key, g, d, lo, hi)
    _, g, d, lo, hi = best
    x = p.filter((pl.col("gameId") == g) & (pl.col("dfn") == d)).sort("ord")
    x = x.with_row_index("idx").slice(lo - 1, hi - lo + 2)
    a = abbrs(league, year).filter(pl.col("gameId") == g).row(0, named=True)
    team = a["abbr_h"] if d == a["home_id"] else a["abbr_a"]
    opp = a["abbr_a"] if d == a["home_id"] else a["abbr_h"]
    return x.select(
        pl.lit(league).alias("league"), pl.lit(lib.pbp_history.season_label(league, year)).alias("season"),
        "gameId", pl.lit(a["game_date"]).alias("game_date"), pl.lit(team).alias("team"),
        pl.lit(opp).alias("opponent"), pl.col("idx").cast(pl.Int32).alias("seq_index"),
        "ord", "period", "start", "end", "pts", "stop")


def record_game() -> pl.DataFrame:
    rec = pl.read_csv(OUT / "records.csv", schema_overrides={"gameId": pl.Utf8})
    r = rec.filter((pl.col("league") == "nba") & (pl.col("rank") == 1)).row(0, named=True)
    league, year = r["league"], r["year"]
    p = pl.read_parquet(POSS / f"{league}_{year}.parquet").filter(pl.col("gameId") == r["gameId"])
    a = abbrs(league, year).filter(pl.col("gameId") == r["gameId"]).row(0, named=True)
    name = {a["home_id"]: a["abbr_h"], a["away_id"]: a["abbr_a"]}
    return p.sort("ord").select(
        pl.lit(league).alias("league"), pl.lit(r["season"]).alias("season"), "gameId",
        pl.lit(a["game_date"]).alias("game_date"), "ord", "period", "start", "end",
        pl.col("off").replace_strict(name, return_dtype=pl.Utf8).alias("offense"),
        pl.col("dfn").replace_strict(name, return_dtype=pl.Utf8).alias("defense"),
        "pts", "abbr_ok")


def perm_example() -> pl.DataFrame:
    lead = pl.read_csv(OUT / "leaders.csv")
    top = lead.filter((pl.col("ranked_by") == "kill_rate") & (pl.col("league") == "nba")
                      & (pl.col("rank") == 1)).row(0, named=True)
    ts = pl.read_csv(OUT / "team_seasons.csv").filter(
        (pl.col("league") == top["league"]) & (pl.col("season") == top["season"])
        & (pl.col("team") == top["team"])).row(0, named=True)
    p = stops_frame(ts["league"], ts["year"]).filter(pl.col("dfn") == ts["team_id"])
    g = p.group_by("gameId").agg(n=pl.len(), S=pl.col("stop").sum()).sort("gameId")
    pmf = lib.season_pmf_perm(list(zip(g["n"].to_list(), g["S"].to_list())))
    mean = float(sum(k * v for k, v in enumerate(pmf)))
    assert abs(mean - ts["exp_game"]) < 1e-6, (mean, ts["exp_game"])
    obs = int(ts["kills"])
    ks = [k for k in range(obs - WINDOW, obs + WINDOW + 1) if 0 <= k < len(pmf)]
    return pl.DataFrame({"league": [ts["league"]] * len(ks), "season": [ts["season"]] * len(ks),
                         "team": [ts["team"]] * len(ks), "kills": ks,
                         "prob": [float(pmf[k]) for k in ks]}).with_columns(pl.col("prob").round(15))


def compute() -> dict[str, pl.DataFrame]:
    return {"example_strip": example_strip(), "record_game": record_game(),
            "perm_example": perm_example()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    res = compute()
    if args.check:
        fails = [f"{n}.csv differs from a fresh build" for n, df in res.items()
                 if not lib.frames_match(df, pl.read_csv(OUT / f"{n}.csv", schema_overrides=df.schema),
                                         tol=1e-12)]
        for f in fails:
            print("FAIL", f)
        print("EXAMPLES", "FAILED" if fails else
              f"PASSED: {', '.join(f'{n} {df.height} rows' for n, df in res.items())}")
        return 1 if fails else 0
    for n, df in res.items():
        df.write_csv(OUT / f"{n}.csv")
        print("wrote", n, df.height, "rows")
    with pl.Config(tbl_rows=40):
        print(res["example_strip"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
