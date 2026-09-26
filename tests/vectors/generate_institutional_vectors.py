"""
Generates tests/vectors/institutional_vectors.json from the Python
reference implementation (waqt.institutional). NOT hand-typed: every
`expected` block is the engine's own answer, frozen. Re-run after any
intentional change to waqt/institutional and review the diff; never
hand-edit the JSON.

Usage: python3 tests/vectors/generate_institutional_vectors.py

WHAT MAKES THESE VECTORS PORTABLE
----------------------------------
Sprint 7's calendar arithmetic (week/fiscal-year/academic-year rules)
is, by design, location-independent and astronomy-independent — it
only needs a Hijri<->Gregorian mapping (see waqt/institutional/rules.py's
module docstring). So instead of freezing a solar day table (Sprint 6's
approach), each vector freezes a CALENDAR TABLE: every day of every
Hijri month the vector's rule touches, as {day, gregorian, weekday}
triples produced by the reference HijriProvider. An implementation in
another language needs no Hijri arithmetic at all: it reads the table,
applies the rule semantics in docs/INSTITUTIONAL.md, and must
reproduce `expected` exactly.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from waqt.calendar_providers import UmmAlQuraProvider
from waqt.hijri import ArithmeticTabularProvider
from waqt.institutional.academic_year import AcademicCalendar, HolidayDefinition, TermDefinition
from waqt.institutional.fiscal_year import FiscalCalendar
from waqt.institutional.rules import MonthDay, MonthEnd, NthWeekdayOfMonth, gregorian_weekday_of, month_days
from waqt.institutional.week import WeekDefinition, week_dates
from datetime import date

TABULAR = ArithmeticTabularProvider()
UAQ = UmmAlQuraProvider()
PROVIDERS = {"arithmetic-tabular": TABULAR, "umm-al-qura": UAQ}

vectors = []


def month_table(provider, year, months):
    out = {}
    for m in months:
        out[str(m)] = [
            {"day": d.day, "gregorian": provider.to_gregorian(d.year, d.month, d.day).isoformat(),
             "weekday": gregorian_weekday_of(provider, d)}
            for d in month_days(provider, year, m)
        ]
    return out


def add(id_, group, description, context, operation, expected):
    assert id_ not in {v["id"] for v in vectors}, f"duplicate id {id_}"
    vectors.append({"id": id_, "group": group, "description": description,
                     "context": context, "operation": operation, "expected": expected})


# ---------------------------------------------------------------------------
# Group: rules (month_day / month_end / nth_weekday_of_month)
# ---------------------------------------------------------------------------

for pname, provider in PROVIDERS.items():
    year = 1448
    ctx = {"calendar_provider": pname, "hijri_year": year, "month_table": month_table(provider, year, [1, 8, 12])}

    d = MonthDay(month=1, day=1).resolve(year, provider)
    g = provider.to_gregorian(d.year, d.month, d.day)
    add(f"rule-month-day-muharram-1-{pname}", "rules", "1 Muharram (month start)", ctx,
        {"op": "month_day", "month": 1, "day": 1},
        {"hijri": d.iso_like(), "gregorian": g.isoformat()})

    d = MonthEnd(month=12).resolve(year, provider)
    g = provider.to_gregorian(d.year, d.month, d.day)
    add(f"rule-month-end-dhul-hijjah-{pname}", "rules", "End of Dhu al-Hijjah (29 or 30)", ctx,
        {"op": "month_end", "month": 12},
        {"hijri": d.iso_like(), "gregorian": g.isoformat()})

    d = NthWeekdayOfMonth(weekday="al-Ahad", n=1, month=1).resolve(year, provider)
    g = provider.to_gregorian(d.year, d.month, d.day)
    add(f"rule-first-ahad-muharram-{pname}", "rules", "First Ahad of Muharram", ctx,
        {"op": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1},
        {"hijri": d.iso_like(), "gregorian": g.isoformat()})

    d = NthWeekdayOfMonth(weekday="al-Khamis", n=-1, month=8).resolve(year, provider)
    g = provider.to_gregorian(d.year, d.month, d.day)
    add(f"rule-last-khamis-shaban-{pname}", "rules", "Last Khamis of Sha'ban", ctx,
        {"op": "nth_weekday_of_month", "weekday": "al-Khamis", "n": -1, "month": 8},
        {"hijri": d.iso_like(), "gregorian": g.isoformat()})

    d = NthWeekdayOfMonth(weekday="al-Jumuah", n=2, month=1).resolve(year, provider)
    g = provider.to_gregorian(d.year, d.month, d.day)
    add(f"rule-second-jumuah-muharram-{pname}", "rules", "2nd Jumu'ah of Muharram (arbitrary positive n)", ctx,
        {"op": "nth_weekday_of_month", "weekday": "al-Jumuah", "n": 2, "month": 1},
        {"hijri": d.iso_like(), "gregorian": g.isoformat()})

# ---------------------------------------------------------------------------
# Group: week (pure Gregorian arithmetic, no Hijri table needed at all —
# context is empty on purpose, proving weeks need no calendar provider)
# ---------------------------------------------------------------------------

WEEK_CASES = [
    ("2026-09-19", "al-Ahad"),      # a Saturday, default (Sunday-first) week
    ("2026-09-13", "al-Ahad"),      # a Sunday itself
    ("2026-09-18", "al-Ahad"),      # a Friday
    ("2026-09-19", "al-Ithnayn"),   # Monday-first convention
]
for i, (d_str, first_day) in enumerate(WEEK_CASES):
    defn = WeekDefinition(first_day=first_day)
    d = date.fromisoformat(d_str)
    wd = week_dates(d, defn)
    add(f"week-dates-{i}", "week", f"Week containing {d_str}, first_day={first_day}", {},
        {"op": "week_dates", "date": d_str, "first_day": first_day},
        {"week_dates": [x.isoformat() for x in wd], "weekdays": [defn.ordered_days()[k] for k in range(7)]})

# ---------------------------------------------------------------------------
# Group: fiscal_year
# ---------------------------------------------------------------------------

for pname, provider in PROVIDERS.items():
    for year in (1447, 1448):
        fc = FiscalCalendar(start_rule=MonthDay(1, 1), end_rule=MonthEnd(12), calendar_provider=provider)
        fy = fc.year(year)
        ctx = {"calendar_provider": pname, "hijri_year": year, "month_table": month_table(provider, year, [1, 12])}
        add(f"fiscal-year-default-{pname}-{year}", "fiscal_year", "Muharram 1 -> end of Dhu al-Hijjah", ctx,
            {"op": "fiscal_year", "start_rule": {"type": "month_day", "month": 1, "day": 1},
             "end_rule": {"type": "month_end", "month": 12}, "year": year},
            {"start": {"hijri": fy.start_hijri.iso_like(), "gregorian": fy.start_gregorian.isoformat()},
             "end": {"hijri": fy.end_hijri.iso_like(), "gregorian": fy.end_gregorian.isoformat()}})

    # custom rule: first Ahad of Rajab (7) -> end of Ramadan (9)
    year = 1448
    fc = FiscalCalendar(start_rule=NthWeekdayOfMonth("al-Ahad", 1, 7), end_rule=MonthEnd(9), calendar_provider=provider)
    fy = fc.year(year)
    ctx = {"calendar_provider": pname, "hijri_year": year, "month_table": month_table(provider, year, [7, 9])}
    add(f"fiscal-year-custom-{pname}", "fiscal_year", "Custom: first Ahad of Rajab -> end of Ramadan", ctx,
        {"op": "fiscal_year", "start_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 7},
         "end_rule": {"type": "month_end", "month": 9}, "year": year},
        {"start": {"hijri": fy.start_hijri.iso_like(), "gregorian": fy.start_gregorian.isoformat()},
         "end": {"hijri": fy.end_hijri.iso_like(), "gregorian": fy.end_gregorian.isoformat()}})

# ---------------------------------------------------------------------------
# Group: academic_year (with terms)
# ---------------------------------------------------------------------------

for pname, provider in PROVIDERS.items():
    year = 1448
    ac = AcademicCalendar(
        opening_rule=NthWeekdayOfMonth("al-Ahad", 1, 1),
        closing_rule=NthWeekdayOfMonth("al-Khamis", -1, 8),
        term_rules=(
            TermDefinition("Term 1", NthWeekdayOfMonth("al-Ahad", 1, 1), MonthDay(3, 29)),
            TermDefinition("Term 2", MonthDay(4, 1), NthWeekdayOfMonth("al-Khamis", -1, 8)),
        ),
        calendar_provider=provider,
    )
    ay = ac.year(year)
    ctx = {"calendar_provider": pname, "hijri_year": year, "month_table": month_table(provider, year, [1, 3, 4, 8])}
    add(f"academic-year-{pname}", "academic_year", "First Ahad of Muharram -> last Khamis of Sha'ban, 2 terms", ctx,
        {"op": "academic_year",
         "opening_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1},
         "closing_rule": {"type": "nth_weekday_of_month", "weekday": "al-Khamis", "n": -1, "month": 8},
         "term_rules": [
             {"label": "Term 1", "start_rule": {"type": "nth_weekday_of_month", "weekday": "al-Ahad", "n": 1, "month": 1},
              "end_rule": {"type": "month_day", "month": 3, "day": 29}},
             {"label": "Term 2", "start_rule": {"type": "month_day", "month": 4, "day": 1},
              "end_rule": {"type": "nth_weekday_of_month", "weekday": "al-Khamis", "n": -1, "month": 8}},
         ],
         "year": year},
        {
            "opening": {"hijri": ay.opening_hijri.iso_like(), "gregorian": ay.opening_gregorian.isoformat()},
            "closing": {"hijri": ay.closing_hijri.iso_like(), "gregorian": ay.closing_gregorian.isoformat()},
            "terms": [
                {"label": t.label, "start": {"hijri": t.start_hijri.iso_like(), "gregorian": t.start_gregorian.isoformat()},
                 "end": {"hijri": t.end_hijri.iso_like(), "gregorian": t.end_gregorian.isoformat()}}
                for t in ay.terms
            ],
        })

doc = {
    "spec": "waqt-institutional/0.1",
    "vector_format_version": "1.0",
    "generated_by": "tests/vectors/generate_institutional_vectors.py",
    "note": (
        "Each vector's context.month_table freezes every day of every Hijri "
        "month the operation touches, as (day, gregorian, weekday) triples. "
        "A consumer needs no Hijri arithmetic and no astronomy to reproduce "
        "`expected` -- only the rule semantics in docs/INSTITUTIONAL.md."
    ),
    "vectors": vectors,
}

out = Path(__file__).resolve().parent / "institutional_vectors.json"
out.write_text(json.dumps(doc, indent=2) + "\n")
print(f"wrote {len(vectors)} vectors to {out}")
