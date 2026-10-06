# Differential run (seed 15, 200 random cases + 141-point latitude sweep)

Truth source: JPL DE421 via Skyfield. Cases drawn uniformly from 24 places x 3 years x all times of day.

## Day-boundary error vs DE421 (|open|,|close| worst of the two, seconds)

| implementation | n | median | p95 | max |
|---|---|---|---|---|
| reference | 200 | 1.10 | 3.20 | 4.26 |
| independent | 200 | 0.09 | 0.13 | 0.17 |

## Disagreements with the oracle

- **reference: weekday label differs from civil date of closing Maghrib**: 21 case(s); e.g. r0006 kiritimati got al-Arbiaa want al-Khamis; r0023 chatham got al-Jumuah want as-Sabt; r0027 reykjavik got al-Khamis want al-Jumuah

## High-latitude existence sweep (lon 0, 3 dates, 45.0-68.0 deg N, step 0.5): 0 of 141 points where at least one implementation's set of defined events differs from the oracle

| date | lat | oracle events | reference | independent |
|---|---|---|---|---|
