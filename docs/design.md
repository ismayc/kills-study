# Design

## Question

Is a "kill" (three straight defensive stops, a broadcast and coaching term
with no official stat) a measure of anything beyond a defense's stop rate?
Which defenses piled up the most, and what are the longest stop streaks on
record? From the backlog idea "kills, three defensive stops in a row"
(`../hub/ideas/historical-analysis-ideas.md`, added July 31, 2026).

## Decisions

Made by Chester Ismay on October 19, 2026, before any result was computed:

1. **Its own private repo**, one of three studies built on the shared
   PlayByPlayV3 layer.
2. **Full history** the possession archive allows: NBA 2000-01 to 2024-25,
   WNBA 2009 to 2025, regular season.
3. **Every three stops is a kill**: six straight stops are two kills, five
   are one. Streaks carry across quarters and reset at the final buzzer (the
   backlog's suggested default).

Made while building (October 19, 2026), each for the reason given:

4. **Possessions from the pbpstats archive, points from V3.** The archive's
   possession rows hold no free-throw makes, so a possession's points are the
   scoring team's rises in the V3 running score inside its window, assigned to
   that team's possession (python/lib.py). Points are compared on whole
   seconds because the archive floors its clock; that took points capture from
   98.8-99.3% to at least 99.87% in every season.
5. **The archive's period-start possessions are trusted.** In
   playbyplay-study's live builds, period-start possessions name the wrong
   offense on 37% of their scoring rows; in the archive the listed defense
   scores on 0.5-1.2% of period-start scoring rows (NBA 2024-25, NBA 2000-01,
   WNBA 2009 checked), no worse than other possessions. The live-build seasons
   (NBA 2025-26, WNBA 2026) are left out for that reason.
6. **The game-level baseline is a random permutation, not p = S / n.** A
   first version plugged each game's stop rate into the independence model and
   found kills 1-4 standard deviations below expectation in every NBA season;
   that came from the plug-in, which puts three straight stops at p cubed
   instead of the exact S(S-1)(S-2) / (n(n-1)(n-2)). See
   `docs/findings/plug-in-baseline-overstates-runs.md`.

## Data checks

- Every archive OPPONENT abbreviation matched one of its game's two
  LeagueGameLog teams (0 unmatched in 6.2 million possessions).
- Possession points against every team-game's scored points
  (`output/validation.csv`): at least 99.87% captured per season, 93-99% of
  team-games exact; the rest are free throws outside any possession.
- The longest NBA streak (LAC holding NOK scoreless on 22 straight
  possessions, March 1, 2006, 7:45 of Q3 to 7:50 of Q4) was checked against
  the raw V3 rows: NOK sat on 59 points through that span.
