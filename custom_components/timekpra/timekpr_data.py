"""Pure parsing / calculation helpers for Timekpr-nExT data.

No Home Assistant import here on purpose: these functions are unit-tested
without a Home Assistant install (see ``tests/``).

Timekpr-nExT semantics this module relies on (checked against the upstream
sources, ``server/user/userdata.py`` and ``server/config/configprocessor.py``):

* ``LIMITS_PER_WEEKDAYS`` is **positional on ALLOWED_WEEKDAYS**: the n-th
  limit belongs to the n-th *allowed* day, not to the n-th day of the week
  (``timekpra --help``: "set time limits for all allowed days").
* Time left today = today's limit - ``TIME_SPENT_BALANCE``. The balance is the
  time spent **including manual adjustments** (``timekpra --settimeleft``
  bonus / penalty); ``TIME_SPENT_DAY`` is the raw usage only.
* ``timekpra --userinfo`` prints ``KEY: value`` lines. ``TIME_LEFT_DAY`` is
  computed by the daemon from the saved state (balance + allowed hours, after
  resetting stale day counters); ``ACTUAL_TIME_LEFT_DAY`` is the live value,
  only present while the user is logged in.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

ALL_DAYS = [1, 2, 3, 4, 5, 6, 7]
DEFAULT_DAILY_MINUTES = 60
SECONDS_PER_DAY = 86400

_HOUR_RE = re.compile(r"^!?(\d+)(?:\[(\d+)-(\d+)\])?$")
_USERINFO_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*:\s*(.*)$")
_LAST_CHECKED_FORMAT = "%Y-%m-%d %H:%M:%S"


def to_int(value: Any) -> int | None:
    """Parse an integer (``"3600"``, ``" 12 "``, ``"-60"``); None if invalid."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_hour_entries(raw: str) -> list[tuple[int, int, int]]:
    """Parse timekpra hour string into (hour, minute_start, minute_end) tuples.

    Examples: ``"7[30-59];8;9;20[00-45]"`` →
    ``[(7,30,59), (8,0,59), (9,0,59), (20,0,45)]``
    """
    results: list[tuple[int, int, int]] = []
    if not raw:
        return results
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        m = _HOUR_RE.match(entry)
        if m:
            h = int(m.group(1))
            ms = int(m.group(2)) if m.group(2) is not None else 0
            me = int(m.group(3)) if m.group(3) is not None else 59
            results.append((h, ms, me))
    return results


def valid_hour_range(
    hour_start: int, hour_end: int, minute_start: int, minute_end: int
) -> bool:
    """True when start < end (an empty / inverted range locks the child out
    or makes ``timekpra --setallowedhours`` fail)."""
    if not (0 <= hour_start <= 23 and 0 <= hour_end <= 23):
        return False
    if not (0 <= minute_start <= 60 and 0 <= minute_end <= 60):
        return False
    return hour_start * 60 + minute_start < hour_end * 60 + minute_end


def parse_allowed_days(raw: dict[str, str]) -> list[int]:
    """Allowed weekdays (1=Monday … 7=Sunday).

    A *missing* key means "no restriction" (all days); an *empty* value means
    every day is disabled and must not be shown as "all days allowed".
    """
    if "ALLOWED_WEEKDAYS" not in raw:
        return list(ALL_DAYS)
    days = {
        int(d) for d in raw["ALLOWED_WEEKDAYS"].split(";") if d.strip().isdigit()
    }
    return sorted(d for d in days if 1 <= d <= 7)


def daily_limits_from_config(
    raw: dict[str, str],
    allowed_days: list[int],
    previous: list[int] | None = None,
) -> list[int]:
    """Per-weekday limits in minutes (index 0 = Monday) from the config file.

    Timekpr maps ``LIMITS_PER_WEEKDAYS`` positionally onto the allowed days.
    Disabled days have no limit in Timekpr: keep the previously known value
    for them (so re-enabling the day restores it), else the natural position.
    """
    limits = [
        int(s) // 60
        for s in raw.get("LIMITS_PER_WEEKDAYS", "").split(";")
        if s.strip().isdigit()
    ]
    if previous is not None and len(previous) == 7:
        daily = [int(v) for v in previous]
    else:
        daily = [
            limits[i] if i < len(limits) else DEFAULT_DAILY_MINUTES
            for i in range(7)
        ]
    for idx, day in enumerate(sorted(set(allowed_days))):
        if idx < len(limits) and 1 <= day <= 7:
            daily[day - 1] = limits[idx]
    return daily


def align_limits_for_timekpr(
    daily_minutes: list[int], allowed_days: list[int]
) -> list[int]:
    """Build the ``--settimelimits`` list (minutes) for the given allowed days.

    The first values follow the allowed days (what the daemon reads). The list
    is padded to 7 values with the natural Monday…Sunday values: the daemon
    ignores them, but ``timekpra --settimeleft '='`` indexes this list by
    weekday, so padding keeps that command working on every day.
    With all 7 days allowed this is exactly ``daily_minutes``.
    """
    daily = [int(v) for v in daily_minutes][:7]
    while len(daily) < 7:
        daily.append(DEFAULT_DAILY_MINUTES)
    days = sorted({d for d in allowed_days if 1 <= d <= 7})
    out = [daily[d - 1] for d in days]
    out.extend(daily[i] for i in range(len(days), 7))
    return out


def process_config(
    raw: dict[str, str], previous_daily: list[int] | None = None
) -> dict[str, Any]:
    """Transform the raw ``timekpr.<user>.conf`` key/values into entity data."""
    data: dict[str, Any] = {}

    data["allowed_days"] = parse_allowed_days(raw)

    hours_raw = ""
    for key in ("ALLOWED_HOURS_ALL", "ALLOWED_HOURS_1", "ALLOWED_HOURS_MON"):
        if key in raw:
            hours_raw = raw[key]
            break
    hour_entries = parse_hour_entries(hours_raw)
    hours = [e[0] for e in hour_entries]
    data["hour_start"] = min(hours) if hours else 0
    data["hour_end"] = max(hours) if hours else 23
    data["minute_start"] = hour_entries[0][1] if hour_entries else 0
    data["minute_end"] = hour_entries[-1][2] if hour_entries else 59

    data["daily_limits"] = daily_limits_from_config(
        raw, data["allowed_days"], previous_daily
    )

    week = to_int(raw.get("LIMIT_PER_WEEK", "0"))
    data["weekly_limit"] = week // 3600 if week is not None else 0
    month = to_int(raw.get("LIMIT_PER_MONTH", "0"))
    data["monthly_limit"] = month // 3600 if month is not None else 0

    data["track_inactive"] = raw.get("TRACK_INACTIVE", "False").lower() == "true"
    data["lockout_type"] = raw.get("LOCKOUT_TYPE", "lock").lower()
    return data


def is_valid_config(raw: dict[str, str] | None) -> bool:
    """True when the parsed file really is a Timekpr user config.

    An empty / foreign file (e.g. ``cat`` output swallowed by a failed sudo)
    must not be mistaken for "every limit at its default".
    """
    return bool(raw) and (
        "LIMITS_PER_WEEKDAYS" in raw or "ALLOWED_WEEKDAYS" in raw
    )


def parse_userinfo(raw: str) -> dict[str, str]:
    """Parse ``timekpra --userinfo`` output (``KEY: value`` lines)."""
    info: dict[str, str] = {}
    for line in raw.splitlines():
        m = _USERINFO_RE.match(line.strip())
        if m:
            info[m.group(1)] = m.group(2).strip()
    return info


def _first_int(raw: dict[str, str], *keys: str) -> int | None:
    for key in keys:
        val = to_int(raw.get(key))
        if val is not None:
            return val
    return None


def _cap_by_period_limits(
    left: int,
    week_limit_s: int | None,
    week_spent_s: int | None,
    month_limit_s: int | None,
    month_spent_s: int | None,
) -> int:
    """Timekpr also stops the session when the week / month budget is spent."""
    if week_limit_s is not None and week_spent_s is not None:
        left = min(left, week_limit_s - week_spent_s)
    if month_limit_s is not None and month_spent_s is not None:
        left = min(left, month_limit_s - month_spent_s)
    return max(0, left)


def time_values_from_userinfo(info: dict[str, str]) -> dict[str, Any]:
    """Time values from ``timekpra --userinfo`` (Timekpr's own numbers).

    ``time_remaining`` is only returned when Timekpr provides it, so the
    caller can fall back to the control file otherwise.
    """
    out: dict[str, Any] = {}

    spent_day = _first_int(info, "ACTUAL_TIME_SPENT_DAY", "TIME_SPENT_DAY")
    if spent_day is not None:
        out["time_spent_today"] = max(0, spent_day)

    spent_week = to_int(info.get("TIME_SPENT_WEEK"))
    if spent_week is not None:
        out["time_spent_week"] = max(0, spent_week)

    live_left = to_int(info.get("ACTUAL_TIME_LEFT_DAY"))
    if live_left is not None:
        # Live daemon value: already accounts for adjustments, allowed hours
        # and the week / month budgets.
        out["time_remaining"] = max(0, live_left)
        return out

    saved_left = to_int(info.get("TIME_LEFT_DAY"))
    if saved_left is not None:
        # Saved value accounts for adjustments + allowed hours but not for the
        # week / month budgets: apply them like the daemon does at login.
        out["time_remaining"] = _cap_by_period_limits(
            saved_left,
            to_int(info.get("LIMIT_PER_WEEK")),
            spent_week,
            to_int(info.get("LIMIT_PER_MONTH")),
            to_int(info.get("TIME_SPENT_MONTH")),
        )
    return out


def _parse_last_checked(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip()[:19], _LAST_CHECKED_FORMAT)
    except ValueError:
        return None


def time_values_from_control(
    raw: dict[str, str], config: dict[str, Any], today: date
) -> dict[str, Any]:
    """Fallback when ``--userinfo`` is unavailable: read ``<user>.time``.

    Mirrors the daemon: counters saved on a previous day / week / month are
    stale (the daemon only resets them when the user logs in), and the time
    left is today's limit minus the *balance* (which includes manual
    bonus / penalty adjustments), not minus the raw usage.
    """
    out: dict[str, Any] = {}
    spent_day = _first_int(raw, "TIME_SPENT_DAY", "TIME_SPENT_TODAY", "SECONDS_SPENT")
    balance = to_int(raw.get("TIME_SPENT_BALANCE"))
    spent_week = to_int(raw.get("TIME_SPENT_WEEK"))
    spent_month = to_int(raw.get("TIME_SPENT_MONTH"))

    last = _parse_last_checked(raw.get("LAST_CHECKED"))
    if last is not None:
        last_day = last.date()
        if last_day != today:
            spent_day = 0 if spent_day is not None else None
            balance = 0 if balance is not None else None
        if last_day.isocalendar()[:2] != today.isocalendar()[:2]:
            spent_week = 0 if spent_week is not None else None
        if (last_day.year, last_day.month) != (today.year, today.month):
            spent_month = 0 if spent_month is not None else None

    if spent_day is not None:
        out["time_spent_today"] = max(0, spent_day)
    if spent_week is not None:
        out["time_spent_week"] = max(0, spent_week)

    if balance is None:
        balance = spent_day
    if balance is None:
        return out

    if today.isoweekday() not in config.get("allowed_days", ALL_DAYS):
        out["time_remaining"] = 0
        return out
    daily = config.get("daily_limits") or []
    idx = today.weekday()
    if idx >= len(daily):
        return out
    left = min(int(daily[idx]) * 60 - balance, SECONDS_PER_DAY)

    weekly_h = config.get("weekly_limit")
    monthly_h = config.get("monthly_limit")
    out["time_remaining"] = _cap_by_period_limits(
        left,
        int(weekly_h) * 3600 if weekly_h else None,
        spent_week,
        int(monthly_h) * 3600 if monthly_h else None,
        spent_month,
    )
    return out


def roll_over_stale_time(data: dict[str, Any], today: date) -> None:
    """Day changed while the machine was unreachable: reset today's counters.

    ``time_date`` is the date of the last live read. Without this, yesterday's
    usage / remaining time would keep being shown after midnight until the
    machine comes back online.
    """
    stamp = data.get("time_date")
    if not stamp:
        return
    try:
        last = date.fromisoformat(stamp)
    except (TypeError, ValueError):
        return
    if last == today:
        return
    if data.get("time_spent_today") is not None:
        data["time_spent_today"] = 0
    if last.isocalendar()[:2] != today.isocalendar()[:2] and data.get(
        "time_spent_week"
    ) is not None:
        data["time_spent_week"] = 0
    if today.isoweekday() not in data.get("allowed_days", ALL_DAYS):
        data["time_remaining"] = 0
    else:
        daily = data.get("daily_limits") or []
        idx = today.weekday()
        data["time_remaining"] = (
            min(int(daily[idx]) * 60, SECONDS_PER_DAY) if idx < len(daily) else None
        )
    data["time_date"] = today.isoformat()
