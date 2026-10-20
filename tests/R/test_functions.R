# R/functions.R against the same fixtures as tests/python/test_lib.py.
# Run from tests/R:  Rscript -e 'testthat::test_dir(".")'

source(file.path("..", "..", "R", "functions.R"))

test_that("runs and kills", {
  s <- c(1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1)
  expect_equal(runs(s), c(6, 5, 2))
  expect_equal(kills_of(s), 3)
})

test_that("iid DP matches enumeration", {
  p <- 0.37
  for (n in 1:9) {
    g <- as.matrix(expand.grid(rep(list(0:1), n)))
    w <- apply(g, 1, function(x) prod(ifelse(x == 1, p, 1 - p)))
    k <- apply(g, 1, kills_of)
    m <- sum(w * k)
    e <- expected_kills(n, p)
    expect_equal(e[1], m, tolerance = 1e-12)
    expect_equal(e[2], sum(w * k^2) - m^2, tolerance = 1e-12)
  }
})

test_that("permutation DP matches enumeration", {
  for (n in 1:9) for (S in 0:n) {
    k <- if (S == 0) 0 else apply(combn(n, S), 2, function(pos) { x <- rep(0, n); x[pos] <- 1; kills_of(x) })
    e <- expected_kills_perm(n, S)
    expect_equal(e[1], mean(k), tolerance = 1e-12)
    expect_equal(e[2], mean(k^2) - mean(k)^2, tolerance = 1e-12)
  }
})

test_that("plugging in p overstates expected kills", {
  expect_gt(expected_kills(100, 0.5)[1], expected_kills_perm(100, 50)[1])
  expect_equal(expected_kills_perm(6, 6), c(2, 0))
})

fin <- tibble::tibble(gameId = "0020000001", status = "ok", home_id = 1, away_id = 2,
                      abbr_h = "HOM", abbr_a = "AWY")

test_that("possessions map the defense and order", {
  raw <- tibble::tibble(GAMEID = rep("20000001", 4), PERIOD = c("1", "1", "1", "2"),
                        STARTTIME = c("12:00", "11:40", "11:40", "12:00"),
                        ENDTIME = c("11:40", "11:40", "11:20", "11:50"),
                        OPPONENT = c("HOM", "AWY", "HOM", "XXX"))
  p <- possessions(raw, fin)
  expect_equal(p$start, c(720, 700, 700, 720))
  expect_equal(p$end, c(700, 700, 680, 710))
  expect_equal(p$off, c(2, 1, 2, NA))
  expect_equal(p$ord, 0:3)
  expect_equal(p$abbr_ok, c(TRUE, TRUE, TRUE, FALSE))
})

test_that("points go to the scoring team's possession", {
  poss <- tibble::tibble(gameId = "g", period = 1L, start = c(720, 700, 690), end = c(700, 690, 670),
                         off = c(2, 1, 2), dfn = c(1, 2, 1), ord = 0:2, abbr_ok = TRUE)
  sc <- tibble::tibble(gameId = "g", seq = 1:4, period = 1L, t = c(700, 690, 690, 650),
                       team = c(2, 1, 2, 1), pts = c(2, 2, 3, 1))
  r <- attribute_points(poss, sc)
  expect_equal(r$poss$pts[order(r$poss$ord)], c(2, 2, 3))
  expect_equal(r$unassigned$seq, 4L)
})

test_that("streak table", {
  s <- tibble::tibble(gameId = "g", dfn = 1, ord = seq(0, 14, 2), stop = c(1, 1, 1, 0, 1, 1, 1, 1))
  st <- streak_table(s)
  expect_equal(st$length, c(3L, 4L))
  expect_equal(st$first_ord, c(0, 8))
  expect_equal(st$last_ord, c(4, 14))
})
