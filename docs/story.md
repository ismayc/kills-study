# Is a "kill" anything more than a good stop rate?

Coaches and broadcasters call three defensive stops in a row a "kill," but
no league keeps it as a stat. This study counts every kill in 31,197 NBA
games from 2000-01 to 2025-26 and 3,880 WNBA games from 2009 to 2026,
6,543,543 possessions in all, and asks whether a kill measures anything a
defense's stop rate does not. The short answer: it does not. Kill rate
follows stop rate almost exactly, stops arrive in no streakier an order than
chance would give, and the best kill defenses are the best stop defenses.
The counting does leave a record book worth keeping.

<div class="tiles">
<div class="tile"><div class="label">Explained by stop rate</div>
<div class="value">90%</div>
<div class="sub">Share of the variation in NBA team-season kill rates that stop rate alone accounts for (86% in the WNBA).</div></div>
<div class="tile"><div class="label">Streakiness</div>
<div class="value">-0.16%</div>
<div class="sub">NBA kills against each game's own stops in random order: 661 fewer than expected, z -1.85 (WNBA +0.20%, z +0.83).</div></div>
<div class="tile"><div class="label">Best kill rate</div>
<div class="value">8.60</div>
<div class="sub">Kills per 100 opponent possessions, 2019-20 Milwaukee, also the NBA's best stop rate in the study (54.6%).</div></div>
<div class="tile"><div class="label">Longest stop streak</div>
<div class="value">22</div>
<div class="sub">Straight scoreless opponent possessions, reached twice: LAC against NOK in 2006 and CLE against MIL in 2009.</div></div>
</div>

<div class="eyebrow beat">The question</div>

## Counting a stat that nobody keeps

A stop is an opponent possession that scores no points. Possessions come
from the pbpstats possession archive, so an offensive rebound continues a
possession rather than starting a new one, and points come from the league's
play-by-play score timeline. Every three straight stops is a kill: six in a
row are two kills, and five are one. A streak carries across quarters and
ends at the final buzzer. These rules were fixed on October 19, 2026,
before any result was computed.

{{svg:dg_kill_rules|A real stretch of Houston's defense against Portland on November 22, 2024, one cell per Portland possession. Six straight stops that straddle the break between the third and fourth quarters make two kills, because the count carries over (a reset would leave one). The next five straight stops make one kill, and the last two start nothing.}}

The archive stops at NBA 2024-25 and WNBA 2025. The two newest seasons come
from a second possession builder, corrected two ways and checked against
the archive on four seasons both sources cover (the last section below).
Possession points capture at least 99.85% of every season's points; the rest
are free throws that belong to no possession. Every table was computed in
Python and again in R, and the two agree on every cell.

<div class="eyebrow beat">Kills and stops</div>

## A kill rate is a stop rate in different units

Across team-seasons, the correlation between stop rate and kill rate is
0.948 in the NBA and 0.929 in the WNBA, so stop rate alone explains 90% and
86% of the variation in kill rate. The WNBA's higher kill rate (7.93 per 100
opponent possessions, against 6.87 in the NBA) comes with a higher stop rate
(52.5% against 49.6%).

{{fig:fig1_kill_vs_stop_py|Kill rate against stop rate for every team-season, with each league's highest and lowest kill rate named. The points hug the dotted line that independent possessions would give, the named extremes sit at the ends of that line rather than off it, and the WNBA sits further up the same line because its defenses stop more possessions.}}

<div class="eyebrow beat">Streakiness</div>

## Stops do not cluster

The sharper test holds each game's stops fixed and asks whether they bunch
together. If every ordering of a game's own stops were equally likely, how
many kills should a team have had? An exact calculation answers that, and
because it keeps each game's stop count, it already absorbs opponent
strength, pace, and blowouts.

The chart below runs that calculation for the NBA's best kill defense, and
it shows why the order of stops, not their number, is the test: Milwaukee's
kill total sits inside what its own stops give in random order, far above
what an average defense would get from the same possessions.

{{fig:fig4_perm_baseline_py|The bars are the exact distribution of 2019-20 Milwaukee's season kill total if each game's own stops fell in a random order. Its observed total (solid line) sits inside that distribution, slightly below its center. A league-average kill rate over the same possessions (dotted line) lands far to the left: the distance from average is stop rate, and the order of the stops adds nothing.}}

| League | Team-seasons | Kills | Excess over random order | z | Team-seasons with abs(z) > 1.96 |
|---|---|---|---|---|---|
| NBA | 776 | 407,654 | -661 (-0.16%) | -1.85 | 5.5% |
| WNBA | 221 | 48,310 | +96 (+0.20%) | +0.83 | 4.5% |

About 5% of team-seasons would pass 1.96 by chance alone, and 5.5% and 4.5%
do. They split evenly by direction: in the NBA, 21 team-seasons sit above
+1.96 and 22 below -1.96; in the WNBA, 5 and 5. So no defense strings its
stops together more than its stop rate implies. The WNBA's pooled count
sits at chance. The NBA's is slightly below it, with 18 of 26 seasons under
zero: stops alternate with scores a little more often than random order
would give, by a fraction of a percent. The cause is not tested here.

{{fig:fig2_streak_z_py|Each league-season's z for observed against random-order kills. Seasons scatter around zero inside the dotted lines at plus and minus 1.96; two NBA seasons, 2018-19 (z -2.46) and 2023-24 (z -1.99), fall just below them.}}

{{fig:fig3_kill_rate_py|Kills per 100 opponent possessions by season, observed (solid) against the random-order expectation (dotted). The two lines track each other closely; the year-to-year swings come from stop rates, not from streaks.}}

A first version of this test gave each possession its game's stop rate as
an independent chance, and it made every NBA season look anti-streaky. That
shortcut overstates how often three stops line up, so the study uses the
exact random-order baseline instead.

<div class="eyebrow beat">Leaders</div>

## The best kill defenses are the best stop defenses

The top NBA kill rate is 2019-20 Milwaukee at 8.60 per 100, from the best
stop rate of any NBA team-season here (54.6%), and its own streakiness z is
-0.73. In the WNBA, 2021 Connecticut leads at 9.88 with the league's best
stop rate (57.2%) and a streakiness z of +0.73. The 2003-04 NBA season holds
four of the top seven spots (Detroit, San Antonio, New Jersey, and Indiana).

The Milwaukee comparison above holds across the NBA's top ten: each kill
rate sits close to what its own stops give in random order, and the distance
from the league average comes from stopping more possessions.

{{fig:fig6_leaders_py|The ten best NBA kill rates (dark dots) beside the rate each team's own stops give in random order (light dots), with each team-season's stop-rate rank among all 776 NBA team-seasons. Every one is a top-20 stop defense, and the gaps between observed and random order run in both directions.}}

Of the NBA's top ten, one team-season clears 1.96 on streakiness: 2000-01
San Antonio, at 8.43 kills per 100 and a z of +2.66. The highest of any
team-season is 2012 Los Angeles in the WNBA at +3.03, and the lowest is
2018-19 Dallas in the NBA at -3.79.

<div class="eyebrow beat">Record book</div>

## Twenty-two straight possessions without a point

On March 1, 2006, the Clippers held New Orleans/Oklahoma City scoreless for
22 straight possessions, from 7:45 of the third quarter to 7:50 of the
fourth, starting from 7 points down. Cleveland matched it against Milwaukee
on December 6, 2009, from 4:13 of the first quarter to 5:42 of the second,
also from 7 down. The WNBA record is 21, also reached twice: Minnesota
against Indiana on August 18, 2017, and Indiana against Seattle on June 22,
2023.

{{fig:fig5_record_margin_py|The Clippers' score margin through the March 1, 2006 game against New Orleans/Oklahoma City. The shaded span is the 22 straight scoreless opponent possessions, from 7:45 of the third quarter to 7:50 of the fourth; the Clippers went from 7 points down to 15 up inside it and won by 22.}}

<div class="eyebrow beat">Newest seasons</div>

## A second possession source, checked before it was used

NBA 2025-26 and WNBA 2026 come from live-feed possession builds. As stored,
those builds hold empty end-of-period stubs and give period-start
possessions to the wrong team, which would add 0.35 to 0.43 kills per 100 to
every team on the overlap seasons, a false jump in the newest seasons.
Corrected, they reproduce the archive's team kill rates with a correlation
of at least 0.995 and mean team differences of -0.018 to +0.029 per 100.
For scale, the spread across teams is 0.47 to 0.97 per 100.

Against that, the NBA's kill rate went from 6.75 in 2024-25 to 6.51 in
2025-26, and the WNBA's from 8.01 in 2025 to 7.33 in 2026, as points per 100
opponent possessions rose from 114.8 to 116.2 and from 104.5 to 108.9. Both
drops are many times the mean builder difference.

<div class="eyebrow beat">Limits</div>

## What this does not show

The random-order baseline treats a game's possessions as interchangeable.
Possessions late in close games or in garbage time are not, which can push
the observed count either way, and the study does not model that. Every
possession counts, including end-of-quarter heaves, as a broadcast would
count them; the study has not measured whether heaves add kills evenly
across teams. Free throws that fall outside any possession, such as
technicals, are not charged to the defense. Record-book margins come from
summed possession points, so they can differ from the true score by an
unassigned free throw. Twelve games that pass the score checks are missing
from the possession sources. And the newest seasons come from a different
builder: a change of a few hundredths of a kill per 100 into them could be
the builder rather than the game.
