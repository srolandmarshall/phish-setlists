from contextlib import contextmanager
from datetime import date
from random import Random
from types import SimpleNamespace

from phish_setlist_maker.experiments import run_generation_experiment


def test_runner_uses_seeded_generators_and_reports_failed_samples():
    sessions = []
    generator_calls = []
    progress = []
    errors = []

    @contextmanager
    def session_factory():
        session = object()
        sessions.append(session)
        yield session

    class FakeGenerator:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.initial_rng_state = kwargs["rng"].getstate()
            generator_calls.append(self)

        def generate(self, **kwargs):
            self.generate_kwargs = kwargs
            seed_value = self.kwargs["rng"].randint(0, 100_000)
            if seed_value == 59_294:
                raise RuntimeError("sample failed")
            return SimpleNamespace(
                sets=[
                    SimpleNamespace(songs=["first", "second"]),
                    SimpleNamespace(songs=["third"]),
                ],
                encore=SimpleNamespace(songs=["encore song"]),
            )

    samples = run_generation_experiment(
        sample_count=3,
        seed_offset=10,
        jamminess=0.5,
        reference_date=date(2023, 12, 31),
        session_factory=session_factory,
        generator_factory=FakeGenerator,
        on_progress=lambda completed, total: progress.append((completed, total)),
        on_error=lambda index, seed, error: errors.append((index, seed, str(error))),
    )

    assert len(sessions) == 1
    assert all(call.kwargs["session"] is sessions[0] for call in generator_calls)
    assert [call.initial_rng_state for call in generator_calls] == [
        Random(seed).getstate() for seed in (10, 11, 12)
    ]
    assert all(call.kwargs["use_ml_features"] is True for call in generator_calls)
    assert all(call.kwargs["jamminess"] == 0.5 for call in generator_calls)
    assert all(
        call.generate_kwargs
        == {
            "reference_date": date(2023, 12, 31),
            "num_sets": 2,
            "include_encore": True,
        }
        for call in generator_calls
    )
    assert progress == [(1, 3), (2, 3), (3, 3)]
    assert [sample.seed for sample in samples] == [10, 12]
    assert all(sample.set_song_counts == (2, 1) for sample in samples)
    assert all(sample.encore_song_count == 1 for sample in samples)
    assert errors == [(1, 11, "sample failed")]


def test_runner_skips_failed_generation_and_preserves_seed_for_successes():
    errors = []

    @contextmanager
    def session_factory():
        yield object()

    class FakeGenerator:
        def __init__(self, *, rng, **_kwargs):
            self.seed_value = rng.randint(0, 100_000)

        def generate(self, **_kwargs):
            if self.seed_value == 21_620:
                raise ValueError("bad sample")
            return SimpleNamespace(
                sets=[SimpleNamespace(songs=["one"]), SimpleNamespace(songs=[])],
                encore=None,
            )

    samples = run_generation_experiment(
        sample_count=3,
        seed_offset=20,
        jamminess=None,
        reference_date=date(2023, 12, 31),
        session_factory=session_factory,
        generator_factory=FakeGenerator,
        on_error=lambda index, seed, error: errors.append((index, seed, str(error))),
    )

    assert [sample.seed for sample in samples] == [20, 22]
    assert all(sample.set_song_counts == (1, 0) for sample in samples)
    assert all(sample.encore_song_count == 0 for sample in samples)
    assert errors == [(1, 21, "bad sample")]
