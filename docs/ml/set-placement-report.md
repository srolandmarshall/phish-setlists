# Set Placement Summary (WIP)

Run `poetry run python scripts/report_set_placement.py` to generate up-to-date statistics for how songs distribute across `set1`, `set2`, `set3`, and `encore`. Songs must appear at least five times (default `--min-appearances 5`) to count as “representative.” For JSON output suitable for notebooks, add `--format json`.

## Snapshot (2025-10-20)

```
=== Set Placement Overview ===

[encore]
  total tracks   : 3,054
  distinct songs : 343
  top songs:
    - Tweezer Reprise (p=0.626, count=211)
    - Rocky Top (p=0.575, count=119)
    - Good Times Bad Times (p=0.422, count=97)
    - Contact (p=0.471, count=82)
    - Sleeping Monkey (p=0.760, count=73)
    - Fire (p=0.529, count=73)
    - Character Zero (p=0.280, count=73)
    - Loving Cup (p=0.455, count=70)
    - Golgi Apparatus (p=0.145, count=70)
    - Sweet Adeline (p=0.362, count=63)

[set1]
  total tracks   : 18,871
  distinct songs : 643
  top songs:
    - Stash (p=0.818, count=378)
    - Divided Sky (p=0.827, count=367)
    - Bouncing Around the Room (p=0.673, count=332)
    - Foam (p=0.865, count=307)
    - Possum (p=0.504, count=291)
    - Reba (p=0.691, count=289)
    - Chalk Dust Torture (p=0.541, count=285)
    - Runaway Jim (p=0.669, count=275)
    - Cavern (p=0.545, count=264)
    - You Enjoy Myself (p=0.395, count=251)

[set2]
  total tracks   : 15,453
  distinct songs : 719
  top songs:
    - Mike's Song (p=0.660, count=370)
    - Hold Your Head Up (p=0.850, count=357)
    - Tweezer (p=0.780, count=354)
    - Weekapaug Groove (p=0.657, count=348)
    - You Enjoy Myself (p=0.548, count=348)
    - Harry Hood (p=0.743, count=329)
    - Also Sprach Zarathustra (p=0.829, count=228)
    - Possum (p=0.392, count=226)
    - David Bowie (p=0.454, count=223)
    - Chalk Dust Torture (p=0.417, count=220)

[set3]
  total tracks   : 767
  distinct songs : 248
  top songs:
    - Auld Lang Syne (p=0.800, count=24)
    - Suzy Greenberg (p=0.037, count=17)
    - Run Like an Antelope (p=0.034, count=17)
    - Harry Hood (p=0.034, count=15)
    - Slave to the Traffic Light (p=0.048, count=14)
    - Whipping Post (p=0.245, count=12)
    - David Bowie (p=0.024, count=12)
    - Mike's Song (p=0.021, count=12)
    - You Enjoy Myself (p=0.019, count=12)
    - Big Black Furry Creature from Mars (p=0.078, count=11)

=== Song distribution across sets ===
  Songs appearing in 1 sets: 119
  Songs appearing in 2 sets: 140
  Songs appearing in 3 sets: 94
  Songs appearing in 4 sets: 36
```

Append future outputs beneath this snapshot to track changes over time.
