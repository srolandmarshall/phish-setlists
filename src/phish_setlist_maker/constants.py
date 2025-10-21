"""Project-wide constants and enumerations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Tuple


@dataclass(frozen=True)
class EraDefinition:
    """Represents an era with a human label and date bounds."""

    label: str
    start: date
    end: date

    def contains(self, target: date) -> bool:
        return self.start <= target <= self.end


ERA_DEFINITIONS: Dict[str, EraDefinition] = {
    "1.0": EraDefinition("1.0", date(1983, 1, 1), date(1999, 12, 31)),
    "2.0": EraDefinition("2.0", date(2000, 1, 1), date(2004, 8, 15)),
    "3.0": EraDefinition("3.0", date(2009, 3, 6), date(2021, 7, 27)),
    "4.0": EraDefinition("4.0", date(2021, 7, 28), date(2100, 12, 31)),
}


SET_ALIASES: Dict[str, Tuple[str, ...]] = {
    "set1": ("1", "I"),
    "set2": ("2", "II"),
    "set3": ("3", "III"),
    "encore": ("E", "Encore"),
}


DEFAULT_SET_LENGTHS: Dict[str, int] = {
    "set1": 10,
    "set2": 9,
    "set3": 6,
    "encore": 2,
}

# Target runtimes in seconds. Two-set shows lean on the baseline values;
# three-set shows use the overrides defined below.
DEFAULT_SET_DURATION_TARGETS: Dict[str, Tuple[int, int]] = {
    "set1": (80 * 60, 100 * 60),  # 90 ±10 minutes
    "set2": (80 * 60, 100 * 60),
    "set3": (80 * 60, 100 * 60),
    "encore": (15 * 60, 25 * 60),  # 20 ±5 minutes
}

THREE_SET_DURATION_OVERRIDES: Dict[str, Tuple[int, int]] = {
    "set1": (50 * 60, 70 * 60),  # ~60 ±10 minutes
    "set2": (50 * 60, 70 * 60),
    "set3": (50 * 60, 70 * 60),
}
