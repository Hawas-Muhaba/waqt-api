"""
Sprint 7 conformance: tests/vectors/institutional_vectors.json.

Same three-part guarantee Sprint 6 established for scheduling vectors:

1. REGRESSION   every vector re-derives, exactly, through the live
                Python engine.
2. COMPLETENESS the vector's own month_table actually contains every
                day the engine touched to answer it.
3. INDEPENDENCE the JavaScript consumer in consumers/js — which shares
                no code with this package — reproduces every vector
                using only the frozen month_table, no Hijri arithmetic
                of its own.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from waqt.calendar_providers import UmmAlQuraProvider
from waqt.hijri import ArithmeticTabularProvider
from waqt.institutional.academic_year import AcademicCalendar
from waqt.institutional.fiscal_year import FiscalCalendar
from waqt.institutional.rules import gregorian_weekday_of, month_days, rule_from_dict
from waqt.institutional.week import WeekDefinition, week_dates
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "tests" / "vectors" / "institutional_vectors.json").read_text())["vectors"]

PROVIDERS = {"arithmetic-tabular": ArithmeticTabularProvider(), "umm-al-qura": UmmAlQuraProvider()}


def _run(v) -> dict:
    op = v["operation"]
    kind = op["op"]
    if kind in ("month_day", "month_end", "nth_weekday_of_month"):
        provider = PROVIDERS[v["context"]["calendar_provider"]]
        year = v["context"]["hijri_year"]
        rule = rule_from_dict({"type": op["op"], **{k: val for k, val in op.items() if k != "op"}})
        d = rule.resolve(year, provider)
        g = provider.to_gregorian(d.year, d.month, d.day)
        return {"hijri": d.iso_like(), "gregorian": g.isoformat()}

    if kind == "week_dates":
        defn = WeekDefinition(first_day=op["first_day"])
        d = date.fromisoformat(op["date"])
        wd = week_dates(d, defn)
        return {"week_dates": [x.isoformat() for x in wd], "weekdays": list(defn.ordered_days())}

    if kind == "fiscal_year":
        provider = PROVIDERS[v["context"]["calendar_provider"]]
        fc = FiscalCalendar(start_rule=rule_from_dict(op["start_rule"]), end_rule=rule_from_dict(op["end_rule"]),
                             calendar_provider=provider)
        fy = fc.year(op["year"])
        return {"start": {"hijri": fy.start_hijri.iso_like(), "gregorian": fy.start_gregorian.isoformat()},
                "end": {"hijri": fy.end_hijri.iso_like(), "gregorian": fy.end_gregorian.isoformat()}}

    if kind == "academic_year":
        provider = PROVIDERS[v["context"]["calendar_provider"]]
        from waqt.institutional.academic_year import TermDefinition
        terms = tuple(TermDefinition(t["label"], rule_from_dict(t["start_rule"]), rule_from_dict(t["end_rule"]))
                      for t in op["term_rules"])
        ac = AcademicCalendar(opening_rule=rule_from_dict(op["opening_rule"]), closing_rule=rule_from_dict(op["closing_rule"]),
                               term_rules=terms, calendar_provider=provider)
        ay = ac.year(op["year"])
        return {
            "opening": {"hijri": ay.opening_hijri.iso_like(), "gregorian": ay.opening_gregorian.isoformat()},
            "closing": {"hijri": ay.closing_hijri.iso_like(), "gregorian": ay.closing_gregorian.isoformat()},
            "terms": [{"label": t.label, "start": {"hijri": t.start_hijri.iso_like(), "gregorian": t.start_gregorian.isoformat()},
                       "end": {"hijri": t.end_hijri.iso_like(), "gregorian": t.end_gregorian.isoformat()}} for t in ay.terms],
        }
    raise AssertionError(f"unknown op {kind}")


@pytest.mark.parametrize("v", VECTORS, ids=[v["id"] for v in VECTORS])
def test_vector_reproduces_exactly_through_the_live_engine(v):
    assert _run(v) == v["expected"]


_TABLE_VECTORS = [v for v in VECTORS if v["context"].get("month_table")]


@pytest.mark.parametrize("v", _TABLE_VECTORS, ids=[v["id"] for v in _TABLE_VECTORS])
def test_month_table_is_complete_for_its_own_operation(v):
    """Every Hijri month the operation touches is actually in the vector's
    own table -- proves the table really is a sufficient, portable input."""
    provider = PROVIDERS[v["context"]["calendar_provider"]]
    year = v["context"]["hijri_year"]
    for month_str, days in v["context"]["month_table"].items():
        expected_days = month_days(provider, year, int(month_str))
        assert len(days) == len(expected_days)
        for entry, hd in zip(days, expected_days):
            assert entry["day"] == hd.day
            assert entry["gregorian"] == provider.to_gregorian(hd.year, hd.month, hd.day).isoformat()
            assert entry["weekday"] == gregorian_weekday_of(provider, hd)


def test_vector_file_shape_and_coverage():
    assert len(VECTORS) >= 20
    assert len({v["id"] for v in VECTORS}) == len(VECTORS), "vector ids must be unique"
    groups = {v["group"] for v in VECTORS}
    assert groups >= {"rules", "week", "fiscal_year", "academic_year"}
    ops = {v["operation"]["op"] for v in VECTORS}
    assert ops >= {"month_day", "month_end", "nth_weekday_of_month", "week_dates", "fiscal_year", "academic_year"}


def test_week_vectors_need_no_calendar_provider_at_all():
    """Structural: week arithmetic is pure Gregorian-civil-date math --
    its vectors carry an EMPTY context, proving no Hijri table is needed."""
    for v in VECTORS:
        if v["group"] == "week":
            assert v["context"] == {}


NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js not installed; the independent JS consumer cannot run here")
def test_independent_javascript_consumer_validates_all_vectors():
    """Sprint 7 acceptance criterion: a non-Python implementation that
    shares no code with the reference reproduces every institutional
    vector from its own frozen month_table."""
    js = ROOT / "consumers" / "js"
    r = subprocess.run(
        [NODE, "--test", "test/institutional_vectors.test.mjs"],
        cwd=js, capture_output=True, text=True, timeout=180,
    )
    tail = "\n".join(r.stdout.splitlines()[-12:]) + r.stderr[-800:]
    assert r.returncode == 0, tail
    summary = {line.split()[1]: int(line.split()[2]) for line in r.stdout.splitlines() if line.startswith("# ") and line.split()[1] in ("tests", "pass", "fail")}
    assert summary.get("fail", 0) == 0 and summary["pass"] == summary["tests"] >= 20, summary
