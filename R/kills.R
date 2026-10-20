# The whole kills pipeline in R, written from the docstrings of python/lib.py,
# 01_possessions.py, and 02_kills.py. It reads the archive's possession rows
# (data/raw_possessions/, written by 01_possessions.py as read) and the shared
# prepared events, assigns points itself, and writes an _r twin of every
# committed output. python/03_reconcile.py compares them cell by cell.
#
# Run from the repo root:  Rscript R/kills.R

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})
source("R/functions.R")

ARCHIVE <- Sys.getenv("PBP_ARCHIVE", "../.pbp-archive")
Z <- 1.959963984540054

read_finals <- function(league, year) {
  read_csv(file.path(ARCHIVE, "events", sprintf("%s_%d_rs_finals.csv", league, year)),
           col_types = cols(gameId = col_character(), abbr_h = col_character(),
                            abbr_a = col_character(), status = col_character(),
                            game_date = col_character(), .default = col_double()),
           progress = FALSE)
}

memo_iid <- new.env()
iid <- function(n, p) {
  key <- sprintf("%d_%.12f", n, round(p, 12))
  if (is.null(memo_iid[[key]])) memo_iid[[key]] <- expected_kills(n, round(p, 12))
  memo_iid[[key]]
}
memo_perm <- new.env()
perm <- function(n, S) {
  key <- sprintf("%d_%d", n, S)
  if (is.null(memo_perm[[key]])) memo_perm[[key]] <- expected_kills_perm(n, S)
  memo_perm[[key]]
}

one_season <- function(league, year) {
  lg <- league; yr <- year; sl <- season_label(league, year)
  fin <- read_finals(league, year)
  raw <- nanoparquet::read_parquet(file.path("data", "raw_possessions", sprintf("%s_%d.parquet", league, year)))
  ev <- nanoparquet::read_parquet(file.path(ARCHIVE, "events", sprintf("%s_%d_rs.parquet", league, year)),
                                  col_select = c("gameId", "seq", "period", "secs_left", "actionType",
                                                 "location", "score_h", "score_a", "home_id", "away_id",
                                                 "isFieldGoal", "teamId"))
  live <- sprintf("%s_%d", league, year) %in% names(LIVE)
  poss <- if (live) live_possessions(raw, fin, ev) else possessions(raw, fin)
  ev <- ev |> filter(gameId %in% poss$gameId)
  sc <- scoring_events(ev)
  ap <- attribute_points(poss, sc)
  out <- ap$poss
  tot <- sc |> group_by(gameId, team) |> summarise(all = sum(pts), .groups = "drop")
  got <- out |> group_by(gameId, team = off) |> summarise(pts = sum(pts), .groups = "drop")
  cmp <- tot |> left_join(got, by = c("gameId", "team")) |> mutate(pts = coalesce(pts, 0))
  val <- tibble(league = league, year = year, season = season_label(league, year),
                source = if (live) "live" else "archive",
                games_ok = sum(fin$status == "ok"), games = n_distinct(poss$gameId),
                possessions = nrow(poss), abbr_unmatched = sum(!poss$abbr_ok),
                points_captured = round(sum(cmp$pts) / sum(cmp$all), 12),
                team_games_exact = round(mean(cmp$pts == cmp$all), 12),
                unassigned = nrow(ap$unassigned))

  p <- out |> filter(abbr_ok) |> arrange(gameId, ord) |>
    group_by(gameId) |> mutate(t1 = min(off)) |>
    mutate(p1 = ifelse(off == t1, pts, 0), p2 = ifelse(off != t1, pts, 0),
           b1 = cumsum(p1) - p1, b2 = cumsum(p2) - p2) |> ungroup() |>
    mutate(margin_before = ifelse(dfn == t1, b1 - b2, b2 - b1),
           stop = as.integer(pts == 0)) |>
    arrange(gameId, dfn, ord)
  st <- streak_table(p)
  tg <- p |> group_by(gameId, dfn) |>
    summarise(n = n(), stops = sum(stop), pts = sum(pts), .groups = "drop") |>
    left_join(st |> group_by(gameId, dfn) |> summarise(kills = sum(length %/% 3), .groups = "drop"),
              by = c("gameId", "dfn")) |>
    mutate(kills = coalesce(kills, 0L))
  ts <- tg |> group_by(dfn) |> group_modify(function(g, key) {
    n <- sum(g$n); s <- sum(g$stops); ps <- s / n
    es <- 0; vs <- 0; eg <- 0; vg <- 0
    for (i in seq_len(nrow(g))) {
      a <- iid(g$n[i], ps); es <- es + a[1]; vs <- vs + a[2]
      b <- perm(g$n[i], g$stops[i]); eg <- eg + b[1]; vg <- vg + b[2]
    }
    k <- sum(g$kills)
    tibble(games = nrow(g), opp_poss = n, stops = s, stop_rate = ps, kills = k,
           kill_rate = 100 * k / n, share_in_kill = 3 * k / n,
           pts_allowed_per100 = 100 * sum(g$pts) / n, exp_season = es, var_season = vs,
           exp_game = eg, var_game = vg, z_season = (k - es) / sqrt(vs), z_game = (k - eg) / sqrt(vg))
  }) |> ungroup() |>
    transmute(league = lg, year = yr, season = sl, team_id = dfn,
              games, opp_poss, stops, stop_rate, kills, kill_rate, share_in_kill, pts_allowed_per100,
              exp_season, var_season, exp_game, var_game, z_season, z_game)
  first <- p |> select(gameId, dfn, ord, start_period = period, start_clock = start, margin_start = margin_before)
  last <- p |> select(gameId, dfn, ord, end_period = period, end_clock = end)
  st <- st |> inner_join(first, by = c("gameId", "dfn", first_ord = "ord")) |>
    inner_join(last, by = c("gameId", "dfn", last_ord = "ord")) |>
    mutate(league = lg, year = yr)
  meta <- fin |> filter(status == "ok") |>
    transmute(gameId, year = yr, game_date, home_id, away_id, abbr_h, abbr_a, league = lg)
  list(val = val, ts = ts, st = st, meta = meta,
       tg = tg |> transmute(league = lg, year = yr, gameId, dfn, n, stops))
}

res <- unlist(lapply(names(YEARS), function(lg) lapply(YEARS[[lg]], function(y) one_season(lg, y))),
              recursive = FALSE)
val <- bind_rows(lapply(res, `[[`, "val"))
write_csv(val, "output/validation_r.csv")
meta <- bind_rows(lapply(res, `[[`, "meta"))
abbr <- bind_rows(meta |> transmute(league, year, team_id = home_id, team = abbr_h),
                  meta |> transmute(league, year, team_id = away_id, team = abbr_a)) |>
  count(league, year, team_id, team) |> arrange(league, year, team_id, desc(n), team) |>
  group_by(league, year, team_id) |> slice(1) |> ungroup() |> select(-n)
ts <- bind_rows(lapply(res, `[[`, "ts")) |> left_join(abbr, by = c("league", "year", "team_id")) |>
  arrange(league, year, team_id) |>
  group_by(league, year) |> mutate(kill_rate_z = (kill_rate - mean(kill_rate)) / sd(kill_rate)) |>
  ungroup()
write_csv(ts, "output/team_seasons_r.csv")

st <- bind_rows(lapply(res, `[[`, "st")) |>
  inner_join(meta |> select(-league, -year), by = "gameId") |>
  mutate(team = ifelse(dfn == home_id, abbr_h, abbr_a),
         opponent = ifelse(dfn == home_id, abbr_a, abbr_h),
         season = mapply(season_label, league, year)) |>
  select(league, year, season, gameId, game_date, team, opponent, length, start_period,
         start_clock, margin_start, end_period, end_clock)
ordered <- st |> arrange(desc(length), game_date, gameId, team)
records <- bind_rows(lapply(names(YEARS), function(lg) ordered |> filter(league == lg) |> head(25) |>
  mutate(rank = 1:25)))
write_csv(records, "output/records_r.csv")
season_records <- ordered |> group_by(league, year) |> slice(1) |> ungroup() |> arrange(league, year)
write_csv(season_records, "output/season_records_r.csv")

ls <- ts |> group_by(league, year, season) |>
  summarise(teams = n(), opp_poss = sum(opp_poss), kills = sum(kills), exp_season = sum(exp_season),
            var_season = sum(var_season), exp_game = sum(exp_game), var_game = sum(var_game),
            .groups = "drop") |>
  mutate(kill_rate = 100 * kills / opp_poss, excess_season = kills - exp_season,
         excess_game = kills - exp_game, z_season = excess_season / sqrt(var_season),
         z_game = excess_game / sqrt(var_game)) |>
  arrange(league, year)
write_csv(ls, "output/league_seasons_r.csv")

lead <- bind_rows(lapply(names(YEARS), function(lg) bind_rows(lapply(c("kill_rate", "kill_rate_z"), function(by)
  ts |> filter(league == lg) |> arrange(desc(.data[[by]]), year, team_id) |> head(15) |>
    transmute(ranked_by = by, rank = 1:15, league, season, team, kill_rate, kill_rate_z, stop_rate,
              pts_allowed_per100, z_game)))))
write_csv(lead, "output/leaders_r.csv")

# The exact random-order distribution of kills for the NBA's top kill rate
# (python/07_examples.py writes the Python twin, perm_example.csv).
top <- lead |> filter(ranked_by == "kill_rate", league == "nba", rank == 1)
tsr <- ts |> filter(league == top$league, season == top$season, team == top$team)
tgr <- bind_rows(lapply(res, `[[`, "tg")) |>
  filter(league == tsr$league, year == tsr$year, dfn == tsr$team_id) |> arrange(gameId)
pmf <- season_pmf_perm(tgr$n, tgr$stops)
stopifnot(abs(sum((seq_along(pmf) - 1) * pmf) - tsr$exp_game) < 1e-6)
ks <- (tsr$kills - 100):(tsr$kills + 100)
ks <- ks[ks >= 0 & ks < length(pmf)]
write_csv(tibble(league = tsr$league, season = tsr$season, team = tsr$team, kills = ks,
                 prob = round(pmf[ks + 1], 15)), "output/perm_example_r.csv")

summ <- bind_rows(lapply(names(YEARS), function(lg) {
  x <- ts |> filter(league == lg)
  k <- sum(x$kills)
  r <- cor(x$stop_rate, x$kill_rate)
  tibble(league = lg, team_seasons = nrow(x), kills = k,
         excess_season = k - sum(x$exp_season), z_season = (k - sum(x$exp_season)) / sqrt(sum(x$var_season)),
         excess_game = k - sum(x$exp_game), z_game = (k - sum(x$exp_game)) / sqrt(sum(x$var_game)),
         share_abs_z_over_1_96 = mean(abs(x$z_game) > Z), corr_stop_kill = r, r2_stop_kill = r * r)
}))
write_csv(summ, "output/summary_r.csv")
cat("R pipeline:", nrow(ts), "team-seasons,", nrow(st), "streaks\n")
