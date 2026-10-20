# Data sources

One row per dataset. A dataset is not used until its **License** cell is filled
from the source's own page (quote it), or marked "unverified" with the reason.
Raw play-by-play and possession rows stay local (`../.pbp-archive/` and
`data/` are outside git); this repo publishes only team-season aggregates and
record tables.

| Dataset | URL | License (quoted) | Commercial use | Redistribution | Retrieved | Local file |
|---|---|---|---|---|---|---|
| pbpstats possession archives, NBA 2000-01 to 2024-25 and WNBA 2009 to 2025 regular season (`pbpstats_*`, `wnba_pbpstats_*`) | https://github.com/shufinskiy/nba_data | Repository: "Apache License 2.0" (GitHub license metadata). The possessions are built by the pbpstats library from stats.nba.com play-by-play, so NBA.com terms govern the data: unverified | no (personal research) | no: kept in `../.pbp-archive/raw/`, outside git | October 19, 2026 | `../.pbp-archive/raw/*pbpstats*.tar.xz` (sha256 in `raw/checksums.txt`) |
| `PlayByPlayV3` archives, the same seasons (`nbastatsv3_*`, `wnba_nbastatsv3_*`) | https://github.com/shufinskiy/nba_data | as above | no | no | October 19, 2026 | `../.pbp-archive/raw/*nbastatsv3*.tar.xz` |
| LeagueGameLog team-game finals and abbreviations | https://stats.nba.com/stats/leaguegamelog (harvested by playoff-series-study) | unverified: NBA.com terms of use | no | no | October 2026 | `../playoff-series-study/data/raw/gamelogs/*_rs.csv` |
