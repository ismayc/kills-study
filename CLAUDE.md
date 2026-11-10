# Kills study

Is a "kill" (three straight defensive stops) a measure beyond a defense's
stop rate? NBA 2000-01 to 2025-26 and WNBA 2009 to 2026. Personal research in
the basketball-data-science family (backlog: `../hub/ideas/historical-analysis-ideas.md`,
"kills, three defensive stops in a row"). Decisions and their dates:
`docs/design.md`. Public repo; keep findings and working notes out of it.

## Data context

- **Sources:** pbpstats possession archive (read with
  `../basketball-analysis-tools/pbp_history.py`) and the shared PlayByPlayV3
  layer for points; only finals status `ok` games.
- **Grain:** possessions: `gameId`, `ord` (game order), with `off`, `dfn`,
  `pts`. Sequences: one defense in one game. Outputs: team-season, league
  season, streak records.
- **Keys:** `gameId` 10-character text; archive years are season start
  years; the archive's OPPONENT is the defense.
- **Definitions:** `python/lib.py` and its R twin `R/functions.R`. Kills =
  floor(run / 3); streaks carry across quarters, reset at the final buzzer.
- **Known issues:** archive clock floored to whole seconds (compare on
  floored V3 time); free throws outside any possession are unassigned; NBA
  2025-26 and WNBA 2026 come from playbyplay-study's live builds with two
  corrections (`lib.live_possessions`), gated by `python/06_source_check.py`
  on the four overlap seasons. Never add a live season without that gate.
- **Sources of truth:** each team-game's scored points (V3, itself checked
  against LeagueGameLog finals).
- **Suspicious results:** points captured under 99.5% in a season, a streak
  over 25, or a streakiness z beyond 4 means stop and check.

Data sources and licenses: `DATA_SOURCES.md`. Raw rows stay local.

## How work is done here

- Family layout: `python/NN_*.py`, `python/lib.py` with its R twin,
  `R/kills.R` for the full R pipeline (about 2 minutes), tests in both
  languages (brute-force enumeration for both DPs), `output/` committed,
  `run_checks.sh` as the gate. Python uses polars and plotly; the shared venv
  is `../.venv`.
- Python and R agree on every reconciled cell within 1e-9: methods are exact
  DPs, no simulation.
- Streak tests that condition on an observed count use the permutation
  baseline, never a plug-in rate (`docs/design.md`, decision 6).
- README results are generated (`python/05_report.py`); never type a number
  into them.
- **Plan mode first** for any step that drops games or possessions, changes
  the stop or kill definition, or joins tables. Label anything not checked
  against data as unverified.
