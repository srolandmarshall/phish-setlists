# Song Transition Summary (WIP)

Run `poetry run python scripts/report_song_transitions.py` to list the most frequent song-to-song transitions within each canonical set (`set1`, `set2`, `set3`, `encore`).

Flags:
- `--min-count` (default `10`): minimum number of shows required for a transition to appear.
- `--top` (default `15`): how many transitions to show per set.
- `--format json`: emit machine-readable output for notebooks.

## Snapshot (2025-10-20)

```
=== Frequent Song Transitions ===

[set1]
  I Am Hydrogen → Weekapaug Groove (129 shows)
  Mike's Song → I Am Hydrogen (126 shows)
  Colonel Forbin's Ascent → Fly Famous Mockingbird (77 shows)
  The Oh Kee Pa Ceremony → Suzy Greenberg (76 shows)
  The Horse → Silent in the Morning (72 shows)
  Runaway Jim → Foam (53 shows)
  Alumni Blues → Letter to Jimmy Page (44 shows)
  Dinner and a Movie → Bouncing Around the Room (37 shows)
  Letter to Jimmy Page → Alumni Blues (35 shows)
  Sparkle → Stash (31 shows)
  The Man Who Stepped Into Yesterday → Avenu Malkenu (31 shows)
  Buried Alive → Poor Heart (30 shows)
  The Oh Kee Pa Ceremony → AC/DC Bag (29 shows)
  Avenu Malkenu → The Man Who Stepped Into Yesterday (29 shows)
  Divided Sky → Cavern (28 shows)

[set2]
  I Am Hydrogen → Weekapaug Groove (197 shows)
  Mike's Song → I Am Hydrogen (188 shows)
  The Horse → Silent in the Morning (75 shows)
  The Oh Kee Pa Ceremony → Suzy Greenberg (54 shows)
  Mike's Song → Simple (45 shows)
  Hold Your Head Up → Love You (45 shows)
  The Man Who Stepped Into Yesterday → Avenu Malkenu (36 shows)
  Hold Your Head Up → Terrapin (28 shows)
  Harry Hood → Cavern (26 shows)
  Love You → Hold Your Head Up (26 shows)
  Avenu Malkenu → The Man Who Stepped Into Yesterday (25 shows)
  Colonel Forbin's Ascent → Fly Famous Mockingbird (24 shows)
  Terrapin → Hold Your Head Up (22 shows)
  Cracklin' Rosie → Hold Your Head Up (22 shows)
  Hold Your Head Up → Bike (21 shows)

[set3]
  <no transitions meeting the threshold>

[encore]
  Sleeping Monkey → Tweezer Reprise (25 shows)
  Sleeping Monkey → Rocky Top (15 shows)
  Contact → Big Black Furry Creature from Mars (13 shows)
  Loving Cup → Tweezer Reprise (12 shows)
  The Horse → Silent in the Morning (10 shows)
```

Append future outputs below to track how the strongest historical transitions evolve.
