"""
waqt.scheduling — Sprint 6: Islamic scheduling & deadline engine.

Temporal primitives (points, windows, deadlines) over the Waqt day and
its astronomical events. Sits ABOVE waqt.semantics and waqt.core; it
changes neither, and adds no astronomy and no calendar dependence.

See docs/SCHEDULING.md for the specification this package implements.
"""

from .context import SchedulingContext, day_to_table_entry
from .engine import (
    DayBounds,
    DeadlineCheck,
    Evaluation,
    EventPositionResult,
    Measure,
    NextEventResult,
    ResolvedInterval,
    ResolvedPoint,
    SchedulingEngine,
    SpanClassification,
)
from .model import (
    DAY_SHIFT,
    EVENT_NAMES,
    Anchor,
    Event,
    Fraction,
    Instant,
    Interval,
    NextEvent,
    Offset,
    Point,
    Position,
    PrevEvent,
    RuleError,
    Status,
    UndefinedPolicy,
    after,
    before,
    between,
    interval_from_dict,
    point_from_dict,
    until_next,
    waqt_hours,
    within,
    within_day,
)

from .ops import OPS, run_operation
