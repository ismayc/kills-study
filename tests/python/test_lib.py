"""python/lib.py against hand-built fixtures and brute-force enumeration.
tests/R/test_functions.R asserts the same results for R/functions.R."""
from __future__ import annotations

import importlib.util
import itertools
import sys
from pathlib import Path

import polars as pl
import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def lib():
    spec = importlib.util.spec_from_file_location("kills_lib", REPO / "python" / "lib.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kills_lib"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_runs_and_kills(lib):
    seq = [1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1]
    assert lib.runs(seq) == [6, 5, 2]
    assert lib.kills_of(seq) == 3  # six stops are two kills, five are one
    assert lib.kills_of([]) == 0


def test_iid_dp_matches_enumeration(lib):
    for n in range(1, 10):
        p = 0.37
        m = v = 0.0
        for seq in itertools.product([0, 1], repeat=n):
            w = 1.0
            for x in seq:
                w *= p if x else 1 - p
            k = lib.kills_of(list(seq))
            m += w * k
            v += w * k * k
        em, ev = lib.expected_kills(n, p)
        assert em == pytest.approx(m, abs=1e-12)
        assert ev == pytest.approx(v - m * m, abs=1e-12)


def test_permutation_dp_matches_enumeration(lib):
    for n in range(1, 10):
        for S in range(n + 1):
            ks = [lib.kills_of([1 if i in pos else 0 for i in range(n)])
                  for pos in itertools.combinations(range(n), S)]
            m = sum(ks) / len(ks)
            em, ev = lib.expected_kills_perm(n, S)
            assert em == pytest.approx(m, abs=1e-12)
            assert ev == pytest.approx(sum(k * k for k in ks) / len(ks) - m * m, abs=1e-12)


def test_plugging_in_p_overstates_expected_kills(lib):
    # The reason the game baseline is a permutation, not p = S / n.
    assert lib.expected_kills(100, 0.5)[0] > lib.expected_kills_perm(100, 50)[0]
    assert lib.expected_kills_perm(6, 6) == (2.0, 0.0)


def finals():
    return pl.DataFrame({"gameId": ["0020000001"], "status": ["ok"], "home_id": [1], "away_id": [2],
                         "abbr_h": ["HOM"], "abbr_a": ["AWY"]})


def test_possessions_map_the_defense_and_order(lib):
    raw = pl.DataFrame({"GAMEID": ["20000001"] * 4, "PERIOD": ["1", "1", "1", "2"],
                        "STARTTIME": ["12:00", "11:40", "11:40", "12:00"],
                        "ENDTIME": ["11:40", "11:40", "11:20", "11:50"],
                        "OPPONENT": ["HOM", "AWY", "HOM", "XXX"]})
    p = lib.possessions(raw, finals())
    # Zero-length possession (11:40 to 11:40) sorts before the one it precedes.
    assert p.select("period", "start", "end", "off", "dfn", "ord").rows() == [
        (1, 720.0, 700.0, 2, 1, 0), (1, 700.0, 700.0, 1, 2, 1), (1, 700.0, 680.0, 2, 1, 2),
        (2, 720.0, 710.0, None, None, 3)]
    assert p["abbr_ok"].to_list() == [True, True, True, False]


def test_points_go_to_the_scoring_teams_possession(lib):
    poss = pl.DataFrame({"gameId": ["g"] * 3, "period": [1, 1, 1], "start": [720.0, 700.0, 690.0],
                         "end": [700.0, 690.0, 670.0], "off": [2, 1, 2], "dfn": [1, 2, 1],
                         "ord": [0, 1, 2], "abbr_ok": [True] * 3})
    sc = pl.DataFrame({"gameId": ["g"] * 4, "seq": [1, 2, 3, 4], "period": [1] * 4,
                       "t": [700.0, 690.0, 690.0, 650.0], "team": [2, 1, 2, 1], "pts": [2, 2, 3, 1]})
    out, un = lib.attribute_points(poss, sc)
    # seq 2 (team 1 at 690) belongs to possession 1, whose window ends at 690;
    # seq 3 (team 2 at 690) to possession 2, which starts at 690, not
    # possession 0; seq 4 (team 1 at 650) fits no team-1 possession.
    assert out.sort("ord")["pts"].to_list() == [2, 2, 3]
    assert un["seq"].to_list() == [4]


def test_streak_table(lib):
    seq = pl.DataFrame({"gameId": ["g"] * 8, "dfn": [1] * 8, "ord": list(range(0, 16, 2)),
                        "stop": [1, 1, 1, 0, 1, 1, 1, 1]})
    st = lib.streak_table(seq)
    assert st.select("length", "first_ord", "last_ord").rows() == [(3, 0, 4), (4, 8, 14)]


def test_frames_match_tolerates_noise_but_not_differences(lib):
    a = pl.DataFrame({"k": ["x", "y"], "n": [1, 2], "v": [0.5, 0.25]})
    assert lib.frames_match(a, a.with_columns(pl.col("v") + 1e-13))
    assert not lib.frames_match(a, a.with_columns(pl.col("v") + 1e-6))
    assert not lib.frames_match(a, a.with_columns(pl.col("n") + 1))
    assert not lib.frames_match(a, a.with_columns(pl.lit("z").alias("k")))
    assert not lib.frames_match(a, a.head(1))
    assert not lib.frames_match(a, a.with_columns(pl.lit(None, pl.Float64).alias("v")))


def live_fixture():
    raw = pl.DataFrame({
        "game_id": [22500001] * 5, "PERIOD": [1, 1, 1, 2, 2],
        "start_secs": [720.0, 700.0, 0.0, 720.0, 690.0], "end_secs": [700.0, 690.0, 0.0, 690.0, 670.0],
        # Period 1 starts listed as team 1 (wrong); the 0:00 stub is empty;
        # period 2's start has no field-goal attempt or turnover, so its
        # listed offense stands.
        "offense_team_id": [1, 1, 2, 2, 1], "FGA": [1, 1, 0, 0, 1], "TURNOVERS": [0, 0, 0, 0, 0],
        "FTA": [0, 0, 0, 2, 0]})
    fin = pl.DataFrame({"gameId": ["0022500001"], "status": ["ok"], "home_id": [1], "away_id": [2]})
    ev = pl.DataFrame({"gameId": ["0022500001"] * 3, "seq": [1, 2, 3], "period": [1, 1, 2],
                       "secs_left": [710.4, 695.0, 700.0], "isFieldGoal": [1, 1, 0],
                       "actionType": ["Missed Shot", "Made Shot", "Free Throw"], "teamId": [2, 1, 2]})
    return raw, fin, ev


def test_live_possessions_drop_stubs_and_fix_period_starts(lib):
    raw, fin, ev = live_fixture()
    p = lib.live_possessions(raw, fin, ev)
    assert p.select("period", "start", "end", "off", "dfn", "ord").rows() == [
        (1, 720.0, 700.0, 2, 1, 0), (1, 700.0, 690.0, 1, 2, 1),
        (2, 720.0, 690.0, 2, 1, 2), (2, 690.0, 670.0, 1, 2, 3)]
    assert p["abbr_ok"].all()
