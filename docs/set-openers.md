# Historical set openers

Generation uses precomputed first-song frequencies for Set 1, Set 2, and Set 3.
Set 1 is the show opener. Selection is made from songs already selected for
that set, so opener weighting does not add an ineligible song, change set
length, or duplicate a song. The existing closer stays in place. A candidate
is promoted only when the resulting order still satisfies stored song-order,
mandatory-segue, and forbidden-transition constraints.

The feature table stores opener count, total appearances in the same set, and
the resulting conditional probability by era. When an era has fewer than 20
opener observations, generation uses the all-era table. If no generated
candidate has an opener record in the selected era, it also falls back to the
all-era table. The sampling weight is `opening_probability * sqrt(total_count)`
to reduce the influence of low-support outliers.

## Rebuild the feature

After refreshing the source database, regenerate the analytics exports and
feature files. The exported `tracks.parquet` must reflect the refreshed source
data. Then run:

```sh
poetry run python scripts/build_features.py \
  --data-dir data/analytics \
  --out-dir data/analytics/features
```

This writes `data/analytics/features/set_opening_frequencies.parquet`. The
generator loads the table with the other ML features; when the file is missing,
generation keeps its normal song order without error. The table can be inspected
with pandas using `pd.read_parquet(...)`, filtering by `canonical_set` and
`era`; `era == "all"` contains the fallback probabilities.

After replacing feature files on a running API, restart its workers or clear the
process feature-store cache so they load the refreshed table.
