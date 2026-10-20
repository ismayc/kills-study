# The R twins of python/lib.py, written from its docstrings. tests/R pins
# them to the same fixtures as tests/python.

suppressPackageStartupMessages(library(dplyr))

YEARS <- list(nba = 2000:2024, wnba = 2009:2025)

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

streak_table <- function(seq) {
  seq |> group_by(gameId, dfn) |> mutate(brk = cumsum(stop == 0)) |>
    filter(stop == 1) |> group_by(gameId, dfn, brk) |>
    summarise(length = n(), first_ord = first(ord), last_ord = last(ord), .groups = "drop") |>
    select(-brk)
}
