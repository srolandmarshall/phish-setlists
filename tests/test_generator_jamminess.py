"""Fast regression checks for explicit jamminess intensity bands."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from phish_setlist_maker.generator.core import SetlistGenerator


@pytest.mark.parametrize(
    ("jamminess", "expected_percentile"),
    [
        (0.0, "p30"),
        (0.249, "p30"),
        (0.25, "p50"),
        (0.499, "p50"),
        (0.5, "p70"),
        (0.749, "p70"),
        (0.75, "p90"),
        (1.0, "p90"),
    ],
)
def test_explicit_jamminess_selects_expected_duration_percentile(
    db_session,
    jamminess: float,
    expected_percentile: str,
) -> None:
    """Boundary values select the documented historical duration distribution."""
    distributions = {
        "p30": {"Song": 180.0},
        "p50": {"Song": 300.0},
        "p70": {"Song": 420.0},
        "p90": {"Song": 540.0},
    }
    statistics = SimpleNamespace(
        song_durations_p30=distributions["p30"],
        song_durations_p50=distributions["p50"],
        song_durations_p70=distributions["p70"],
        song_durations_p90=distributions["p90"],
    )
    generator = SetlistGenerator(db_session, jamminess=jamminess)

    selected = generator._select_duration_map_by_intensity(
        statistics,
        current_duration=0.0,
        duration_target=None,
    )

    assert selected == distributions[expected_percentile]
