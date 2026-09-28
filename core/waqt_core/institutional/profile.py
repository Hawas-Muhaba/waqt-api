"""
waqt.institutional.profile — CalendarProfile: Sprint 7's explicit,
data-only configuration object.

Per the brief:

    CalendarProfile
        name
        calendar_provider
        week_definition
        fiscal_year_definition
        academic_year_definition
        timezone_policy
        labeling_rules

    "But profiles should be data/configuration, not buried in the core
    algorithms."

`CalendarProfile` is a plain frozen dataclass composed entirely of
values already defined elsewhere in this package (a `HijriProvider`,
a `WeekDefinition`, a `FiscalCalendar`, an `AcademicCalendar`) plus two
free-form dict fields — `timezone_policy`, `labeling_rules` — for
institution-specific settings this sprint does not standardize (which
timezone provider/override to use; how to render labels). Nothing in
`waqt/core.py`, `waqt/solar.py`, or `waqt/scheduling/` reads a
CalendarProfile; it exists purely so an application can bundle one
institution's choices into one named, swappable object instead of
threading five separate parameters through every call.

`to_dict()`/`from_dict()` round-trip the STRUCTURE (rule shapes,
labels, provider name) as JSON — the calendar_provider itself is
looked up by name via a resolver callable the caller supplies (this
package does not own a provider registry; `waqt.api.providers` already
does, and Sprint 7 reuses it rather than duplicating it — see
`waqt/api/institutional_endpoint.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..hijri import HijriProvider
from .academic_year import AcademicCalendar, HolidayDefinition, TermDefinition, default_islamic_academic_calendar
from .fiscal_year import FiscalCalendar, default_islamic_fiscal_calendar
from .rules import rule_from_dict
from .week import DEFAULT_WEEK, WeekDefinition


@dataclass(frozen=True)
class CalendarProfile:
    name: str
    calendar_provider: HijriProvider
    week_definition: WeekDefinition = DEFAULT_WEEK
    fiscal_year_definition: Optional[FiscalCalendar] = None
    academic_year_definition: Optional[AcademicCalendar] = None
    timezone_policy: dict = field(default_factory=dict)
    labeling_rules: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Every sub-definition, if present, must agree on the same
        # calendar provider as the profile itself — a profile is one
        # institution's one coherent set of choices, not a place to
        # silently mix two providers' dates.
        for sub in (self.fiscal_year_definition, self.academic_year_definition):
            if sub is not None and sub.calendar_provider is not None and sub.calendar_provider is not self.calendar_provider:
                raise ValueError(
                    f"CalendarProfile {self.name!r}: fiscal/academic calendar_provider must be the same "
                    "object as the profile's calendar_provider, or left unset (None)."
                )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "calendar_provider": {"name": self.calendar_provider.name, "version": self.calendar_provider.version},
            "week_definition": self.week_definition.to_dict(),
            "fiscal_year_definition": self.fiscal_year_definition.to_dict() if self.fiscal_year_definition else None,
            "academic_year_definition": self.academic_year_definition.to_dict() if self.academic_year_definition else None,
            "timezone_policy": self.timezone_policy,
            "labeling_rules": self.labeling_rules,
        }


def default_profile(name: str, calendar_provider: HijriProvider) -> CalendarProfile:
    """A ready-made profile using the brief's own fiscal/academic
    examples (see fiscal_year.py / academic_year.py). A convenience,
    not the library's opinion of what every institution should use."""
    return CalendarProfile(
        name=name,
        calendar_provider=calendar_provider,
        week_definition=DEFAULT_WEEK,
        fiscal_year_definition=default_islamic_fiscal_calendar(calendar_provider),
        academic_year_definition=default_islamic_academic_calendar(calendar_provider),
    )


def profile_from_dict(d: dict, resolve_provider: Callable[[str], HijriProvider]) -> CalendarProfile:
    """Build a CalendarProfile from JSON-shaped configuration data.
    `resolve_provider(name)` is supplied by the caller (typically
    `waqt.api.providers.resolve_calendar_provider`) so this module
    never needs its own provider registry."""
    provider = resolve_provider(d["calendar_provider"])
    wk = d.get("week_definition") or {}
    week_def = WeekDefinition(
        first_day=wk.get("first_day", DEFAULT_WEEK.first_day),
        jumuah_day=wk.get("jumuah_day", DEFAULT_WEEK.jumuah_day),
        label=wk.get("label", "default"),
    )

    fy = d.get("fiscal_year_definition")
    fiscal = None
    if fy:
        fiscal = FiscalCalendar(
            start_rule=rule_from_dict(fy["start_rule"]), end_rule=rule_from_dict(fy["end_rule"]),
            label=fy.get("label", "Fiscal Year"), calendar_provider=provider,
        )

    ay = d.get("academic_year_definition")
    academic = None
    if ay:
        academic = AcademicCalendar(
            opening_rule=rule_from_dict(ay["opening_rule"]), closing_rule=rule_from_dict(ay["closing_rule"]),
            term_rules=tuple(
                TermDefinition(t["label"], rule_from_dict(t["start_rule"]), rule_from_dict(t["end_rule"]), t.get("year_offset", 0))
                for t in ay.get("term_rules", [])
            ),
            holidays=tuple(
                HolidayDefinition(h["label"], rule_from_dict(h["rule"]), h.get("year_offset", 0))
                for h in ay.get("holidays", [])
            ),
            label=ay.get("label", "Academic Year"), calendar_provider=provider,
        )

    return CalendarProfile(
        name=d["name"], calendar_provider=provider, week_definition=week_def,
        fiscal_year_definition=fiscal, academic_year_definition=academic,
        timezone_policy=d.get("timezone_policy", {}), labeling_rules=d.get("labeling_rules", {}),
    )
