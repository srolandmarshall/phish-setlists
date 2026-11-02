# Generation cache behavior

## ML feature tables

`get_process_feature_store()` caches the loaded `FeatureStore` once per resolved feature directory in each API worker. Repeated generator instances reuse the in-memory tables instead of rereading Parquet files for each request. Directly constructed `FeatureStore` instances remain independent.

Feature artifacts are immutable for the life of the cache. After replacing files under `data/analytics/features`, call `FeatureStore.clear_cache()` in that worker before the next generation request, or restart the API workers. Each worker has its own process cache.

## Historical segment statistics

Completed segment statistics are cached on the SQLAlchemy `Session` for the active request, keyed by set, cutoff date, era, year, and long-form threshold. Calls requesting different numbers of top sequences reuse the same statistics and return the requested slice. The cache is session-scoped and is not shared across requests, so updated database contents are visible to new request sessions.
