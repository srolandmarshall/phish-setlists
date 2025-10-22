# Venue & Tour Analysis

Run `poetry run python scripts/report_venue_analysis.py` after exporting data to see venue tendencies and tour statistics.

## What's Included

### Venue Tendencies (`venue_tendencies.parquet`)
For each venue that has hosted shows:
- **show_count**: number of shows at this venue
- **track_count**: total tracks performed
- **avg_show_duration**: average show length in seconds
- **top_songs**: list of the 5 most frequently played songs at this venue

### Base Tables
- `venues.parquet`: venue metadata (name, location, coordinates)
- `tours.parquet`: tour metadata (name, date range, show count)

## Snapshot (2025-10-22)

### Top 10 Most Played Venues

**Madison Square Garden** (New York, NY)
- 87 shows, 1,799 tracks, avg 178.5 min
- Top songs: Tweezer, Harry Hood, Weekapaug Groove

**Dick's Sporting Goods Park** (Commerce City, CO)
- 42 shows, 879 tracks, avg 188.8 min
- Top songs: Chalk Dust Torture, Ghost, Harry Hood

**The Front** (Burlington, VT)
- 33 shows, 619 tracks, avg 104.5 min
- Top songs: AC/DC Bag, You Enjoy Myself, Golgi Apparatus

**Deer Creek** (Noblesville, IN)
- 32 shows, 626 tracks, avg 168.3 min
- Top songs: Down with Disease, Run Like an Antelope, Split Open and Melt

**Saratoga Performing Arts Center** (Saratoga Springs, NY)
- 27 shows, 551 tracks, avg 167.9 min
- Top songs: Tweezer Reprise, Chalk Dust Torture, David Bowie

**Alpine Valley Music Theatre** (East Troy, WI)
- 26 shows, 539 tracks, avg 172.8 min
- Top songs: Character Zero, Ghost, Also Sprach Zarathustra

**Hampton Coliseum** (Hampton, VA)
- 24 shows, 489 tracks, avg 173.7 min
- Top songs: Mike's Song, Weekapaug Groove, Harry Hood

**Nectar's** (Burlington, VT)
- 24 shows, 489 tracks, avg 114.3 min
- Top songs: Alumni Blues, Golgi Apparatus, Fluffhead

**Gorge Amphitheatre** (George, WA)
- 22 shows, 423 tracks, avg 173.9 min
- Top songs: Wolfman's Brother, The Moma Dance, Tweezer

**Great Woods Center for the Performing Arts** (Mansfield, MA)
- 22 shows, 413 tracks, avg 158.4 min
- Top songs: Possum, Back on the Train, Harry Hood

### Notable Tours (by show count)

- **1990 Tour**: 145 shows (Jan 20 - Dec 31, 1990)
- **1989 Tour**: 123 shows (Jan 26 - Dec 31, 1989)
- **1988 Tour**: 93 shows (Jan 27 - Dec 17, 1988)
- **Winter/Spring Tour 1993**: 70 shows (Feb 3 - May 8, 1993)
- **Winter/Spring Tour 1991**: 63 shows (Feb 1 - May 19, 1991)

## Use Cases

### Generator Enhancement Ideas
1. **Venue-specific openers**: Use top_songs to weight opening tracks for specific venues
2. **Duration targeting**: Match avg_show_duration when generating for known venues
3. **Regional preferences**: Group venues by state/region to find geographic patterns

### Next Analysis Steps
- Song popularity by venue type (arena vs. theater vs. outdoor)
- Era-specific venue tendencies (how MSG shows evolved over time)
- Correlation between venue size and setlist adventurousness
- Tour momentum analysis (song rotation within a tour)

## Generating Fresh Data

```bash
# Full export (includes venues)
poetry run python scripts/run_analytics_exports.py --use-primary

# Venue-only refresh
poetry run python scripts/build_venue_tour_analysis.py

# View report
poetry run python scripts/report_venue_analysis.py --top-n 20
```
