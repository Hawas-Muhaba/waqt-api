"""waqt_core.display.at_bt.formatter — Presentation-only 12-hour AT/BT formatter.

AT = After Twelve (after midday transit through 23:59:59)
BT = Before Twelve (midnight/opening through 11:59:59)

This module is strictly presentation-only. It does not alter canonical Waqt
times, instants, prayer events, schedules, or day boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time, timedelta
from typing import Any, Optional, Union

# Matches [sign]H...H:MM[:SS]
_TIME_RE = re.compile(r"^([+-])?(\d+):([0-5]\d)(?::([0-5]\d))?$")


@dataclass(frozen=True)
class AtBtTime:
    """Structured representation of an AT/BT formatted time.

    Attributes:
        hour: The 12-hour component (1 to 12).
        minute: The minute component (0 to 59).
        second: The second component (0 to 59) if present, else None.
        period: 'AT' (After Twelve) or 'BT' (Before Twelve).
        day_offset: The day offset relative to the base day (0 for current day,
                    +1 for next day, -1 for previous day, etc.).
        canonical: The canonical time representation string.
        has_seconds: Whether seconds were present in the source input.
    """

    hour: int
    minute: int
    second: Optional[int]
    period: str
    day_offset: int = 0
    canonical: str = ""
    has_seconds: bool = False

    def __post_init__(self) -> None:
        if not (1 <= self.hour <= 12):
            raise ValueError(f"Hour must be 1..12, got {self.hour}")
        if not (0 <= self.minute <= 59):
            raise ValueError(f"Minute must be 0..59, got {self.minute}")
        if self.second is not None and not (0 <= self.second <= 59):
            raise ValueError(f"Second must be 0..59, got {self.second}")
        if self.period not in ("AT", "BT"):
            raise ValueError(f"Period must be 'AT' or 'BT', got {self.period!r}")

    @property
    def display(self) -> str:
        """Render the AT/BT string, explicitly including day offset if non-zero."""
        if self.second is not None:
            time_part = f"{self.hour}:{self.minute:02d}:{self.second:02d}"
        else:
            time_part = f"{self.hour}:{self.minute:02d}"

        suffix = f" {self.period}"
        if self.day_offset > 0:
            offset_text = f" (+{self.day_offset} day{'s' if self.day_offset > 1 else ''})"
            return f"{time_part}{suffix}{offset_text}"
        elif self.day_offset < 0:
            offset_text = f" ({self.day_offset} day{'s' if abs(self.day_offset) > 1 else ''})"
            return f"{time_part}{suffix}{offset_text}"
        return f"{time_part}{suffix}"

    def __str__(self) -> str:
        return self.display


def parse_at_bt(value: Union[str, time, timedelta, int, float, dict[str, Any], Any]) -> AtBtTime:
    """Parse a time value into a structured AtBtTime object.

    Handles:
        - Strings: "HH:MM", "H:MM", "HH:MM:SS", "H:MM:SS", "+HH:MM", "-HH:MM"
        - datetime.time
        - datetime.timedelta
        - int / float (seconds since opening/midnight)
        - dict with 'hour_reading', 'reading', or 'display' keys

    Raises:
        TypeError: If value type is not supported.
        ValueError: If value string or parameters are malformed.
    """
    if isinstance(value, dict):
        str_val = value.get("hour_reading") or value.get("reading") or value.get("display")
        if isinstance(str_val, dict):
            str_val = str_val.get("display")
        if not isinstance(str_val, str):
            raise ValueError(f"Cannot extract time string from dict: {value!r}")
        value = str_val

    if isinstance(value, time):
        canonical = f"{value.hour:02d}:{value.minute:02d}"
        if value.second:
            canonical += f":{value.second:02d}"
        h24 = value.hour
        m = value.minute
        s = value.second if value.second > 0 else None
        has_seconds = s is not None
        day_offset = 0
        hour12, period = _to_12h(h24)
        return AtBtTime(
            hour=hour12,
            minute=m,
            second=s,
            period=period,
            day_offset=day_offset,
            canonical=canonical,
            has_seconds=has_seconds,
        )

    if isinstance(value, timedelta):
        canonical = _format_td_canonical(value)
        total_seconds = int(value.total_seconds())
        return _from_total_seconds(total_seconds, canonical=canonical, has_seconds=True)

    if isinstance(value, (int, float)):
        total_seconds = int(value)
        canonical = _format_seconds_canonical(total_seconds)
        return _from_total_seconds(total_seconds, canonical=canonical, has_seconds=True)

    if isinstance(value, str):
        s_val = value.strip()
        if s_val.startswith("Waqt "):
            s_val = s_val[5:].strip()
        m = _TIME_RE.match(s_val)
        if not m:
            raise ValueError(f"Invalid time format for AT/BT conversion: {value!r}")
        sign_str, h_str, min_str, sec_str = m.groups()
        is_neg = sign_str == "-"
        total_hours = int(h_str)
        minute = int(min_str)
        second = int(sec_str) if sec_str is not None else None
        has_seconds = second is not None

        if is_neg:
            # e.g. -01:30:00 -> -5400 seconds
            sec_val = second if second is not None else 0
            neg_total_seconds = -(total_hours * 3600 + minute * 60 + sec_val)
            return _from_total_seconds(neg_total_seconds, canonical=s_val, has_seconds=has_seconds)

        day_offset = total_hours // 24
        hour_in_day = total_hours % 24
        hour12, period = _to_12h(hour_in_day)
        return AtBtTime(
            hour=hour12,
            minute=minute,
            second=second,
            period=period,
            day_offset=day_offset,
            canonical=s_val,
            has_seconds=has_seconds,
        )

    raise TypeError(f"Unsupported type for AT/BT conversion: {type(value).__name__}")


def format_at_bt(
    value: Union[str, time, timedelta, int, float, dict[str, Any], Any],
    include_seconds: Optional[bool] = None,
) -> str:
    """Format any supported time value into canonical AT/BT presentation string.

    Examples:
        00:00 -> "12:00 BT"
        01:00 -> "1:00 BT"
        11:59 -> "11:59 BT"
        12:00 -> "12:00 AT"
        13:00 -> "1:00 AT"
        17:50 -> "5:50 AT"
        23:59 -> "11:59 AT"
        24:15 -> "12:15 BT (+1 day)"
        25:30 -> "1:30 BT (+1 day)"

    Args:
        value: Time representation (string, time, timedelta, seconds, or dict).
        include_seconds: If True, always format seconds (:ss). If False, omit seconds.
                         If None (default), preserve seconds only if input had them.
    Returns:
        The formatted AT/BT string.
    """
    parsed = parse_at_bt(value)
    if include_seconds is True and parsed.second is None:
        parsed = AtBtTime(
            hour=parsed.hour,
            minute=parsed.minute,
            second=0,
            period=parsed.period,
            day_offset=parsed.day_offset,
            canonical=parsed.canonical,
            has_seconds=True,
        )
    elif include_seconds is False and parsed.second is not None:
        parsed = AtBtTime(
            hour=parsed.hour,
            minute=parsed.minute,
            second=None,
            period=parsed.period,
            day_offset=parsed.day_offset,
            canonical=parsed.canonical,
            has_seconds=False,
        )
    return parsed.display


def _to_12h(hour_in_day: int) -> tuple[int, str]:
    """Convert a 0..23 hour into (hour_12, period)."""
    if hour_in_day == 0:
        return 12, "BT"
    elif 1 <= hour_in_day <= 11:
        return hour_in_day, "BT"
    elif hour_in_day == 12:
        return 12, "AT"
    else:  # 13..23
        return hour_in_day - 12, "AT"


def _from_total_seconds(total_seconds: int, canonical: str, has_seconds: bool) -> AtBtTime:
    """Derive AtBtTime from total signed seconds."""
    # divmod by 86400 handles negative seconds seamlessly in Python (flooring division):
    # e.g. -1800 // 86400 = -1, -1800 % 86400 = 84600 (23:30)
    day_offset, sec_in_day = divmod(total_seconds, 86400)
    h24, rem = divmod(sec_in_day, 3600)
    m, s = divmod(rem, 60)
    hour12, period = _to_12h(h24)
    return AtBtTime(
        hour=hour12,
        minute=m,
        second=s if has_seconds else None,
        period=period,
        day_offset=day_offset,
        canonical=canonical,
        has_seconds=has_seconds,
    )


def _format_td_canonical(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    return _format_seconds_canonical(total_seconds)


def _format_seconds_canonical(total_seconds: int) -> str:
    sign = "-" if total_seconds < 0 else ""
    t = abs(total_seconds)
    h = t // 3600
    m = (t % 3600) // 60
    s = t % 60
    return f"{sign}{h:02d}:{m:02d}:{s:02d}"
