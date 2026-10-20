# The R twins of python/lib.py, written from its docstrings. tests/R pins
# them to the same fixtures as tests/python.

suppressPackageStartupMessages(library(dplyr))

YEARS <- list(nba = 2000:2025, wnba = 2009:2026)

season_label <- function(league, year) {
  if (league == "nba") sprintf("%d-%02d", year, (year + 1) %% 100) else as.character(year)
}

mmss <- function(x) {
  p <- strsplit(x, ":", fixed = TRUE)
  vapply(p, function(v) as.numeric(v[1]) * 60 + as.numeric(v[2]), numeric(1))
}

possessions <- function(raw, finals) {
  ok <- finals |> filter(status == "ok") |> select(gameId, home_id, away_id, abbr_h, abbr_a)
  raw |>
    transmute(gameId = sprintf("%010s", GAMEID), period = as.integer(PERIOD),
              start = mmss(STARTTIME), end = mmss(ENDTIME), opp = OPPONENT) |>
    mutate(gameId = gsub(" ", "0", gameId)) |>
    inner_join(ok, by = "gameId") |>
    mutate(dfn = case_when(opp == abbr_h ~ home_id, opp == abbr_a ~ away_id),
           off = case_when(opp == abbr_h ~ away_id, opp == abbr_a ~ home_id),
           abbr_ok = !is.na(off)) |>
    arrange(gameId, period, desc(start), desc(end), off) |>
    group_by(gameId) |> mutate(ord = as.integer(row_number() - 1L)) |> ungroup() |>
    select(gameId, period, start, end, off, dfn, ord, abbr_ok)
}

scoring_events <- function(ev) {
  ev |> filter(actionType %in% c("Made Shot", "Free Throw"), location %in% c("h", "v")) |>
    mutate(sc = ifelse(location == "h", score_h, score_a)) |>
    group_by(gameId, location) |> mutate(pts = sc - lag(sc, default = 0)) |> ungroup() |>
    mutate(team = ifelse(location == "h", home_id, away_id)) |>
    filter(pts > 0) |>
    transmute(gameId, seq, period, t = floor(secs_left), team, pts)
}

attribute_points <- function(poss, sc) {
  p <- poss |> filter(abbr_ok) |> transmute(gameId, period, ord, start, end, team = off)
  j <- sc |> inner_join(p, by = c("gameId", "period", "team"), relationship = "many-to-many") |>
    filter(t >= end, t <= start) |>
    mutate(strict = t < start) |>
    arrange(gameId, seq, desc(strict), ord) |>
    group_by(gameId, seq) |> slice(1) |> ungroup()
  pts <- j |> group_by(gameId, ord) |> summarise(pts = sum(pts), .groups = "drop")
  list(poss = poss |> left_join(pts, by = c("gameId", "ord")) |> mutate(pts = coalesce(pts, 0)),
       unassigned = sc |> anti_join(j, by = c("gameId", "seq")))
}

runs <- function(stops) {
  r <- rle(stops)
  r$lengths[r$values == 1]
}

kills_of <- function(stops) sum(runs(stops) %/% 3)

expected_kills <- function(n, p) {
  q <- 1 - p
  P <- c(1, 0, 0); M1 <- c(0, 0, 0); M2 <- c(0, 0, 0)
  for (i in seq_len(n)) {
    nP <- c(q * sum(P), p * P[1], p * P[2])
    n1 <- c(q * sum(M1), p * M1[1], p * M1[2])
    n2 <- c(q * sum(M2), p * M2[1], p * M2[2])
    nP[1] <- nP[1] + p * P[3]
    n1[1] <- n1[1] + p * (M1[3] + P[3])
    n2[1] <- n2[1] + p * (M2[3] + 2 * M1[3] + P[3])
    P <- nP; M1 <- n1; M2 <- n2
  }
  m <- sum(M1)
  c(m, sum(M2) - m * m)
}

expected_kills_perm <- function(n, S) {
  if (S == 0 || n == 0) return(c(0, 0))
  P <- matrix(0, S + 1, 3); M1 <- P; M2 <- P
  P[1, 1] <- 1
  s <- 0:S
  for (i in 0:(n - 1)) {
    pstop <- pmin(pmax((S - s) / (n - i), 0), 1)
    pscore <- 1 - pstop
    nP <- matrix(0, S + 1, 3); n1 <- nP; n2 <- nP
    nP[, 1] <- rowSums(pscore * P); n1[, 1] <- rowSums(pscore * M1); n2[, 1] <- rowSums(pscore * M2)
    a <- pstop * P; b <- pstop * M1; cc <- pstop * M2
    up <- 2:(S + 1); dn <- 1:S
    nP[up, 2] <- nP[up, 2] + a[dn, 1]; n1[up, 2] <- n1[up, 2] + b[dn, 1]; n2[up, 2] <- n2[up, 2] + cc[dn, 1]
    nP[up, 3] <- nP[up, 3] + a[dn, 2]; n1[up, 3] <- n1[up, 3] + b[dn, 2]; n2[up, 3] <- n2[up, 3] + cc[dn, 2]
    nP[up, 1] <- nP[up, 1] + a[dn, 3]
    n1[up, 1] <- n1[up, 1] + b[dn, 3] + a[dn, 3]
    n2[up, 1] <- n2[up, 1] + cc[dn, 3] + 2 * b[dn, 3] + a[dn, 3]
    P <- nP; M1 <- n1; M2 <- n2
  }
  m <- sum(M1[S + 1, ])
  c(m, sum(M2[S + 1, ]) - m * m)
}

# P(K = k), k = 0..S %/% 3, under the random-order baseline: the DP of
# expected_kills_perm with the kill count added to the state.
kills_pmf_perm <- function(n, S) {
  K <- S %/% 3
  if (S == 0 || n == 0) return(1)
  # R0, R1, R2: (stops drawn) x (kills so far) for run length mod 3 = 0, 1, 2
  R0 <- matrix(0, S + 1, K + 1); R1 <- R0; R2 <- R0
  R0[1, 1] <- 1
  s <- 0:S
  up <- 2:(S + 1); dn <- 1:S
  for (i in 0:(n - 1)) {
    pstop <- pmin(pmax((S - s) / (n - i), 0), 1)
    pscore <- 1 - pstop
    a0 <- pstop * R0; a1 <- pstop * R1; a2 <- pstop * R2
    N0 <- pscore * (R0 + R1 + R2)
    N1 <- matrix(0, S + 1, K + 1); N2 <- N1
    N1[up, ] <- a0[dn, , drop = FALSE]
    N2[up, ] <- a1[dn, , drop = FALSE]
    if (K > 0) N0[up, 2:(K + 1)] <- N0[up, 2:(K + 1)] + a2[dn, 1:K, drop = FALSE]
    R0 <- N0; R1 <- N1; R2 <- N2
  }
  R0[S + 1, ] + R1[S + 1, ] + R2[S + 1, ]
}

# P(total kills = k), k = 0, 1, ..., for a team-season's games (vectors n and
# S), each game's stops in a random order independently: the convolution of
# the games' kills_pmf_perm, summed directly (no FFT).
season_pmf_perm <- function(n, S) {
  out <- 1
  for (g in seq_along(n)) {
    b <- kills_pmf_perm(n[g], S[g])
    new <- rep(0, length(out) + length(b) - 1)
    for (j in seq_along(b)) {
      idx <- j:(j + length(out) - 1)
      new[idx] <- new[idx] + out * b[j]
    }
    out <- new
  }
  out
}

streak_table <- function(seq) {
  seq |> group_by(gameId, dfn) |> mutate(brk = cumsum(stop == 0)) |>
    filter(stop == 1) |> group_by(gameId, dfn, brk) |>
    summarise(length = n(), first_ord = first(ord), last_ord = last(ord), .groups = "drop") |>
    select(-brk)
}

LIVE <- c("nba_2025" = "nba_2025-26", "wnba_2026" = "wnba_2026")

# A live build's possessions in possessions()' schema, with the two
# corrections in python/lib.py: drop possessions with no field-goal attempt,
# turnover, or free-throw attempt; give each period-start possession to the
# team of the first field-goal attempt or turnover in its window.
live_possessions <- function(raw, finals, ev) {
  ok <- finals |> filter(status == "ok") |> select(gameId, home_id, away_id)
  p <- raw |> filter(FGA + TURNOVERS + FTA > 0) |>
    transmute(gameId = gsub(" ", "0", sprintf("%010s", as.character(game_id))),
              period = as.integer(PERIOD), start = start_secs, end = end_secs,
              listed = as.numeric(offense_team_id)) |>
    inner_join(ok, by = "gameId") |>
    group_by(gameId, period) |> mutate(pstart = start == max(start)) |> ungroup()
  acts <- ev |> filter(isFieldGoal == 1 | actionType == "Turnover", teamId > 0) |>
    transmute(gameId, seq, period, t = floor(secs_left), team = teamId)
  first <- p |> filter(pstart) |> select(gameId, period, start, end) |>
    inner_join(acts, by = c("gameId", "period"), relationship = "many-to-many") |>
    filter(t <= start, t >= end) |>
    arrange(gameId, period, seq) |>
    group_by(gameId, period) |> slice(1) |> ungroup() |>
    select(gameId, period, start, first_team = team)
  p |> left_join(first, by = c("gameId", "period", "start")) |>
    mutate(off = ifelse(pstart & !is.na(first_team), first_team, listed),
           abbr_ok = off == home_id | off == away_id,
           dfn = case_when(off == home_id ~ away_id, off == away_id ~ home_id)) |>
    arrange(gameId, period, desc(start), desc(end), off) |>
    group_by(gameId) |> mutate(ord = as.integer(row_number() - 1L)) |> ungroup() |>
    select(gameId, period, start, end, off, dfn, ord, abbr_ok)
}
