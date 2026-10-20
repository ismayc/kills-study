"""Python against R, every committed output, cell by cell.

R/kills.R maps every archive possession, assigns its points from the shared
prepared events itself, and recomputes every table. Each pair must have the same rows (after sorting on
its key columns) and agree within 1e-9 on every numeric cell and exactly on
every text and integer cell; a missing value must be missing in both.
Exit status 1 on any difference.
"""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
TOL = 1e-9

PAIRS = {
    "validation": ["league", "year"],
    "team_seasons": ["league", "year", "team_id"],
    "league_seasons": ["league", "year"],
    "records": ["league", "rank"],
    "season_records": ["league", "year"],
    "leaders": ["ranked_by", "league", "rank"],
    "summary": ["league"],
    "perm_example": ["league", "season", "team", "kills"],
}


def compare(name: str, keys: list[str]) -> list[str]:
    py = pl.read_csv(OUT / f"{name}.csv", infer_schema_length=None)
    r = pl.read_csv(OUT / f"{name}_r.csv", infer_schema_length=None, null_values=["NA"])
    if py.columns != r.columns:
        return [f"{name}: columns differ: {py.columns} vs {r.columns}"]
    if py.height != r.height:
        return [f"{name}: {py.height} rows vs {r.height}"]
    py = py.sort(keys, nulls_last=True)
    r = r.sort(keys, nulls_last=True)
    fails = []
    for c in py.columns:
        a, b = py[c], r[c]
        if (a.is_null() != b.is_null()).any():
            fails.append(f"{name}.{c}: missing in one language only")
            continue
        if a.dtype.is_float() or b.dtype.is_float():
            d = (a.cast(pl.Float64) - b.cast(pl.Float64)).abs().max()
            if d is not None and d > TOL:
                fails.append(f"{name}.{c}: max difference {d:.3g}")
        elif not (a.cast(pl.Utf8) == b.cast(pl.Utf8)).fill_null(True).all():
            fails.append(f"{name}.{c}: values differ")
    return fails


def main() -> int:
    fails = []
    cells = 0
    for name, keys in PAIRS.items():
        fails += compare(name, keys)
        df = pl.read_csv(OUT / f"{name}.csv")
        cells += df.height * df.width
    for f in fails:
        print("FAIL", f)
    print("RECONCILE", "FAILED" if fails else f"PASSED: {len(PAIRS)} tables, {cells:,} cells")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
