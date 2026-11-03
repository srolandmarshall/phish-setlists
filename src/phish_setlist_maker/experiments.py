"""Reusable mechanics for offline, seeded generation experiments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from random import Random
from typing import Callable, ContextManager

from .db import session_scope
from .generator.core import SetlistGenerator


@dataclass(frozen=True)
class GenerationSample:
    """Small, stable summary of one generated setlist for offline analysis."""

    seed: int
    set_song_counts: tuple[int, ...]
    encore_song_count: int


def run_generation_experiment(
    *,
    sample_count: int,
    seed_offset: int,
    jamminess: float | None,
    reference_date: date,
    on_progress: Callable[[int, int], None] | None = None,
    on_error: Callable[[int, int, Exception], None] | None = None,
    session_factory: Callable[[], ContextManager] = session_scope,
    generator_factory: Callable[..., SetlistGenerator] = SetlistGenerator,
) -> list[GenerationSample]:
    """Generate a reproducible sequence of two-set shows for analysis scripts.

    The runner owns the shared database/session, random seed, generator, and
    failure loop. Consumers own progress formatting and all analysis/reporting.
    Failed generations are skipped, matching the existing script behavior.
    """
    samples: list[GenerationSample] = []
    with session_factory() as session:
        for index in range(sample_count):
            completed = index + 1
            seed = seed_offset + index
            if on_progress is not None:
                on_progress(completed, sample_count)

            generator = generator_factory(
                session=session,
                rng=Random(seed),
                use_ml_features=True,
                jamminess=jamminess,
            )
            try:
                result = generator.generate(
                    reference_date=reference_date,
                    num_sets=2,
                    include_encore=True,
                )
                sample = GenerationSample(
                    seed=seed,
                    set_song_counts=tuple(len(segment.songs) for segment in result.sets),
                    encore_song_count=len(result.encore.songs) if result.encore else 0,
                )
            except Exception as error:
                if on_error is not None:
                    on_error(index, seed, error)
                continue
            samples.append(sample)
    return samples
