"""Shared definitions for the kills study. Every function here has a twin in
R/functions.R, pinned to the same fixtures in tests/python and tests/R.

Possessions
-----------
From the shufinskiy/nba_data pbpstats archive (NBA 2000-01 to 2024-25, WNBA
2009 to 2025): one row per possession (GAMEID, PERIOD, STARTTIME, ENDTIME,
OPPONENT). OPPONENT is the defense's abbreviation; it is matched to the
game's two LeagueGameLog abbreviations, and the other team is the offense.
Times are whole seconds left in the period (the archive floors them).

The two seasons the archive lacks (NBA 2025-26, WNBA 2026) come from
playbyplay-study's builds with the pbpstats library on the liveData feed
(LIVE), with two corrections that make those builds match the archive on
the four seasons both cover (python/06_source_check.py):
  1. possessions with no field-goal attempt, turnover, or free-throw attempt
     are dropped (mostly 0:00 stubs at period ends, which the archive omits);
  2. each period-start possession's offense is the team of the first field
     goal attempt or turnover in its window, because the live builds name
     the wrong offense there (37% of period-start scoring rows in NBA
     2023-24; see playbyplay-study and elam-ending-study).

Points
------
Each scoring event in the shared PlayByPlayV3 layer (the rise in its team's
running score on a Made Shot or Free Throw row) is given to a possession of
the team that scored, in the same period, whose window holds the event's
clock, floored to whole seconds like the archive's: end <= t <= start. When
two possessions qualify (t is one's start and the other's end), the one with
t strictly under its start wins. Scoring that falls in no possession of the
scoring team (technical free throws, free throws at a period's first second)
is left unassigned and counted.

Stops and kills
---------------
A stop is a possession on which the offense scores 0. Each defense's
opponent possessions, in game order (period, then start descending), form
one sequence per game: streaks carry across quarters and reset at the final
buzzer. A run of L straight stops holds floor(L / 3) kills, so six straight
stops are two kills (decided October 19, 2026).

Expected kills with no streakiness
----------------------------------
Two exact baselines, each a dynamic program over the current run length
mod 3:
  - season: each possession a stop with the team-season's stop rate p,
    independently (expected_kills);
  - game: each game's own stops in a uniformly random order
    (expected_kills_perm), which holds each game's stop count fixed and so
    absorbs opponent strength, pace, and blowouts.
Kills above the baseline mean stops cluster; below it, they alternate.
"""
from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT.parent
sys.path.insert(0, str(FAMILY / "basketball-analysis-tools"))
import pbp_history  # noqa: E402

YEARS = {"nba": range(2000, 2026), "wnba": range(2009, 2027)}
RAW_COLS = ["GAMEID", "PERIOD", "STARTTIME", "ENDTIME", "OPPONENT"]
LIVE_DIR = FAMILY / "playbyplay-study" / "data" / "possessions"
# Seasons read from the live builds, and the overlap seasons that check them.
LIVE = {("nba", 2025): "nba_2025-26", ("wnba", 2026): "wnba_2026"}
OVERLAP = {("nba", 2023): "nba_2023-24", ("nba", 2024): "nba_2024-25",
           ("wnba", 2024): "wnba_2024", ("wnba", 2025): "wnba_2025"}
LIVE_COLS = ["game_id", "PERIOD", "start_secs", "end_secs", "offense_team_id",
             "FGA", "TURNOVERS", "FTA"]


def source(league: str, year: int) -> str:
    return "live" if (league, year) in LIVE else "archive"


def live_raw(name: str) -> pl.DataFrame:
    """A live build's possession rows, the columns used, as stored."""
    return pl.read_parquet(LIVE_DIR / f"{name}.parquet", columns=LIVE_COLS)


def live_possessions(raw: pl.DataFrame, finals: pl.DataFrame, ev: pl.DataFrame) -> pl.DataFrame:
    """Typed possessions from a live build, in possessions()' schema, with the
    two corrections in the module docstring. ev: prepared events (gameId,
    seq, period, secs_left, isFieldGoal, actionType, teamId)."""
    ok = finals.filter(pl.col("status") == "ok").select("gameId", "home_id", "away_id")
    p = (raw.filter((pl.col("FGA") + pl.col("TURNOVERS") + pl.col("FTA")) > 0)
            .select(gameId=pl.col("game_id").cast(pl.Utf8).str.zfill(10),
                    period=pl.col("PERIOD").cast(pl.Int32), start="start_secs", end="end_secs",
                    listed=pl.col("offense_team_id").cast(pl.Int64))
            .join(ok, on="gameId", how="inner"))
    p = p.with_columns(pstart=pl.col("start") == pl.col("start").max().over("gameId", "period"))
    acts = (ev.filter(((pl.col("isFieldGoal") == 1) | (pl.col("actionType") == "Turnover"))
                      & (pl.col("teamId") > 0))
              .select("gameId", "seq", "period", t=pl.col("secs_left").floor(), team="teamId"))
    first = (p.filter("pstart").select("gameId", "period", "start", "end")
              .join(acts, on=["gameId", "period"], how="inner")
              .filter((pl.col("t") <= pl.col("start")) & (pl.col("t") >= pl.col("end")))
              .sort("gameId", "period", "seq")
              .group_by("gameId", "period", maintain_order=True).first()
              .select("gameId", "period", "start", first_team="team"))
    p = (p.join(first, on=["gameId", "period", "start"], how="left")
          .with_columns(off=pl.when(pl.col("pstart") & pl.col("first_team").is_not_null())
                              .then(pl.col("first_team")).otherwise(pl.col("listed"))))
    p = p.with_columns(
        abbr_ok=(pl.col("off") == pl.col("home_id")) | (pl.col("off") == pl.col("away_id")))
    p = p.with_columns(dfn=pl.when(pl.col("off") == pl.col("home_id")).then(pl.col("away_id"))
                             .when(pl.col("off") == pl.col("away_id")).then(pl.col("home_id")))
    p = p.sort(["gameId", "period", "start", "end", "off"], descending=[False, False, True, True, False])
    p = p.with_columns(ord=pl.int_range(pl.len()).over("gameId").cast(pl.Int32))
    return p.select("gameId", "period", "start", "end", "off", "dfn", "ord", "abbr_ok")


def mmss(col: str) -> pl.Expr:
    parts = pl.col(col).str.split(":")
    return (parts.list.get(0).cast(pl.Int32) * 60 + parts.list.get(1).cast(pl.Int32)).cast(pl.Float64)


def archive_possessions(league: str, year: int) -> pl.DataFrame:
    """The archive's possessions, one row each, columns as in the archive."""
    d = pbp_history.read_archive(pbp_history.dataset(league, "pbpstats", year))
    return d.select(RAW_COLS).unique(maintain_order=True)


def possessions(raw: pl.DataFrame, finals: pl.DataFrame) -> pl.DataFrame:
    """Typed possessions for games with finals status ok: gameId, period,
    start, end, off, dfn, ord (game order), and abbr_ok (OPPONENT matched one
    of the two teams)."""
    ok = finals.filter(pl.col("status") == "ok").select(
        "gameId", "home_id", "away_id", "abbr_h", "abbr_a")
    p = raw.select(gameId=pl.col("GAMEID").str.zfill(10), period=pl.col("PERIOD").cast(pl.Int32),
                   start=mmss("STARTTIME"), end=mmss("ENDTIME"), opp=pl.col("OPPONENT"))
    p = p.join(ok, on="gameId", how="inner").with_columns(
        dfn=pl.when(pl.col("opp") == pl.col("abbr_h")).then(pl.col("home_id"))
              .when(pl.col("opp") == pl.col("abbr_a")).then(pl.col("away_id")),
        off=pl.when(pl.col("opp") == pl.col("abbr_h")).then(pl.col("away_id"))
              .when(pl.col("opp") == pl.col("abbr_a")).then(pl.col("home_id")))
    p = p.with_columns(abbr_ok=pl.col("off").is_not_null()).sort(
        ["gameId", "period", "start", "end", "off"], descending=[False, False, True, True, False])
    p = p.with_columns(ord=pl.int_range(pl.len()).over("gameId").cast(pl.Int32))
    return p.select("gameId", "period", "start", "end", "off", "dfn", "ord", "abbr_ok")


def scoring_events(ev: pl.DataFrame) -> pl.DataFrame:
    """One row per scoring event: gameId, seq, period, t (whole seconds),
    team, pts."""
    s = ev.filter(pl.col("actionType").is_in(["Made Shot", "Free Throw"])
                  & pl.col("location").is_in(["h", "v"]))
    s = s.with_columns(sc=pl.when(pl.col("location") == "h").then(pl.col("score_h"))
                       .otherwise(pl.col("score_a")))
    s = s.with_columns(
        pts=pl.col("sc") - pl.col("sc").shift(1).over("gameId", "location").fill_null(0),
        team=pl.when(pl.col("location") == "h").then(pl.col("home_id")).otherwise(pl.col("away_id")))
    return s.filter(pl.col("pts") > 0).select(
        "gameId", "seq", "period", t=pl.col("secs_left").floor(), team="team", pts="pts")


def attribute_points(poss: pl.DataFrame, sc: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(possessions with pts, unassigned scoring events)."""
    p = poss.filter(pl.col("abbr_ok"))
    j = (sc.join(p.select("gameId", "period", "ord", "start", "end", team="off"),
                 on=["gameId", "period", "team"], how="inner")
           .filter((pl.col("t") >= pl.col("end")) & (pl.col("t") <= pl.col("start")))
           .with_columns(strict=pl.col("t") < pl.col("start"))
           .sort(["gameId", "seq", "strict", "ord"], descending=[False, False, True, False])
           .group_by("gameId", "seq", maintain_order=True).first())
    pts = j.group_by("gameId", "ord").agg(pts=pl.col("pts").sum())
    out = poss.join(pts, on=["gameId", "ord"], how="left").with_columns(pl.col("pts").fill_null(0))
    return out, sc.join(j.select("gameId", "seq"), on=["gameId", "seq"], how="anti")


def runs(stops: list[int]) -> list[int]:
    """Lengths of the runs of 1s in a 0/1 sequence."""
    out, cur = [], 0
    for s in stops:
        if s:
            cur += 1
        else:
            if cur:
                out.append(cur)
            cur = 0
    if cur:
        out.append(cur)
    return out


def kills_of(stops: list[int]) -> int:
    return sum(L // 3 for L in runs(stops))


@lru_cache(maxsize=None)
def expected_kills(n: int, p: float) -> tuple[float, float]:
    """Mean and variance of the number of kills in n independent possessions,
    each a stop with probability p. State: the current run length mod 3.
    For each state the DP carries P(state), E[K; state], E[K^2; state]; a
    stop that completes a third consecutive stop adds one kill and resets
    the state to 0."""
    q = 1.0 - p
    P = [1.0, 0.0, 0.0]
    M1 = [0.0, 0.0, 0.0]
    M2 = [0.0, 0.0, 0.0]
    for _ in range(n):
        nP, n1, n2 = [0.0] * 3, [0.0] * 3, [0.0] * 3
        for s in range(3):
            if P[s] == 0 and M1[s] == 0 and M2[s] == 0:
                continue
            # a score: back to state 0, no kill
            nP[0] += q * P[s]
            n1[0] += q * M1[s]
            n2[0] += q * M2[s]
            # a stop
            if s < 2:
                nP[s + 1] += p * P[s]
                n1[s + 1] += p * M1[s]
                n2[s + 1] += p * M2[s]
            else:
                nP[0] += p * P[s]
                n1[0] += p * (M1[s] + P[s])
                n2[0] += p * (M2[s] + 2 * M1[s] + P[s])
        P, M1, M2 = nP, n1, n2
    mean = sum(M1)
    return mean, sum(M2) - mean * mean


@lru_cache(maxsize=None)
def expected_kills_perm(n: int, S: int) -> tuple[float, float]:
    """Mean and variance of the number of kills when a game's S stops among
    its n opponent possessions fall in a uniformly random order. This is the
    baseline conditional on the game's own stop count: plugging p = S / n
    into expected_kills instead would put the chance of three straight stops
    at p^3, above the exact S(S-1)(S-2) / (n(n-1)(n-2)), and so overstate
    expected kills. The DP draws possessions without replacement; its state
    is (stops drawn so far, current run length mod 3), vectorized over the
    first coordinate."""
    if S == 0 or n == 0:
        return 0.0, 0.0
    P = np.zeros((S + 1, 3))
    M1 = np.zeros((S + 1, 3))
    M2 = np.zeros((S + 1, 3))
    P[0, 0] = 1.0
    s = np.arange(S + 1, dtype=float)
    for i in range(n):
        left = n - i
        pstop = np.clip((S - s) / left, 0.0, 1.0)[:, None]
        pscore = 1.0 - pstop
        nP, n1, n2 = np.zeros_like(P), np.zeros_like(P), np.zeros_like(P)
        # a score: same stops drawn, state back to 0
        nP[:, 0] += (pscore * P).sum(axis=1)
        n1[:, 0] += (pscore * M1).sum(axis=1)
        n2[:, 0] += (pscore * M2).sum(axis=1)
        # a stop: one more stop drawn
        a, b, c = pstop * P, pstop * M1, pstop * M2
        nP[1:, 1] += a[:-1, 0]
        n1[1:, 1] += b[:-1, 0]
        n2[1:, 1] += c[:-1, 0]
        nP[1:, 2] += a[:-1, 1]
        n1[1:, 2] += b[:-1, 1]
        n2[1:, 2] += c[:-1, 1]
        nP[1:, 0] += a[:-1, 2]
        n1[1:, 0] += b[:-1, 2] + a[:-1, 2]
        n2[1:, 0] += c[:-1, 2] + 2 * b[:-1, 2] + a[:-1, 2]
        P, M1, M2 = nP, n1, n2
    mean = float(M1[S].sum())
    return mean, float(M2[S].sum()) - mean * mean


def streak_table(seq: pl.DataFrame) -> pl.DataFrame:
    """Every run of stops in a defense's game sequence. seq: one row per
    opponent possession with gameId, dfn, ord, stop, period, start, end,
    sorted by gameId, dfn, ord. Returns gameId, dfn, length, first_ord,
    last_ord."""
    s = seq.with_columns(
        brk=(pl.col("stop") == 0).cum_sum().over("gameId", "dfn"))
    r = (s.filter(pl.col("stop") == 1)
          .group_by("gameId", "dfn", "brk", maintain_order=True)
          .agg(length=pl.len(), first_ord=pl.col("ord").first(), last_ord=pl.col("ord").last()))
    return r.drop("brk")


def per100(k: float, n: float) -> float:
    return 100.0 * k / n if n else math.nan


def frames_match(new: pl.DataFrame, old: pl.DataFrame, tol: float = 1e-9) -> bool:
    """The --check comparison: same columns and rows, text and integers
    exact, floats within tol. Exact equality is not used for floats because
    polars group_by aggregates in thread order, so a rerun can move the last
    bit of a mean (seen in this study's team_shots.csv: 2 of 5 reruns)."""
    if new.columns != old.columns or new.height != old.height:
        return False
    for c in new.columns:
        a, b = new[c], old[c]
        if (a.is_null() != b.is_null()).any():
            return False
        if a.dtype.is_float() or b.dtype.is_float():
            d = (a.cast(pl.Float64) - b.cast(pl.Float64)).abs().max()
            if d is not None and d > tol:
                return False
        elif not (a.cast(pl.Utf8) == b.cast(pl.Utf8)).fill_null(True).all():
            return False
    return True
