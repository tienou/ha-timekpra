"""Tests for the pure Timekpr parsing / calculation helpers."""
from __future__ import annotations

from datetime import date

import pytest

from conftest import load

td = load("timekpr_data")

# Issue #3 scenario: 4h allowed today, 1h penalty (timekpra --settimeleft
# gabriel - 3600), 20 min used -> 2h40 left, not 3h40.
USERINFO_LOGGED_OUT = """\
# configuration for user "gabriel":
ALLOWED_HOURS_3: 7;8;9;10;11;12;13;14;15;16;17;18;19;20;21
ALLOWED_WEEKDAYS: 1;2;3;4;5;6;7
LIMITS_PER_WEEKDAYS: 14400;14400;14400;14400;14400;14400;14400
TRACK_INACTIVE: False
HIDE_TRAY_ICON: False
LOCKOUT_TYPE: lock
LIMIT_PER_WEEK: 604800
LIMIT_PER_MONTH: 2678400
TIME_SPENT_BALANCE: 4800
TIME_SPENT_DAY: 1200
TIME_SPENT_WEEK: 1200
TIME_SPENT_MONTH: 1200
TIME_LEFT_DAY: 9600
PLAYTIME_LEFT_DAY: 0
PLAYTIME_SPENT_DAY: 0
"""

USERINFO_LOGGED_IN = USERINFO_LOGGED_OUT + """\
ACTUAL_TIME_SPENT_SESSION: 600
ACTUAL_TIME_INACTIVE_SESSION: 0
ACTUAL_TIME_SPENT_BALANCE: 5400
ACTUAL_TIME_SPENT_DAY: 1800
ACTUAL_TIME_LEFT_DAY: 9000
ACTUAL_TIME_LEFT_CONTINUOUS: 9000
ACTUAL_PLAYTIME_LEFT_DAY: 0
"""


# ── --userinfo ─────────────────────────────────────────────────────


def test_parse_userinfo_skips_comments_and_keeps_values():
    info = td.parse_userinfo(USERINFO_LOGGED_OUT)
    assert "configuration for user" not in "".join(info)
    assert info["TIME_LEFT_DAY"] == "9600"
    assert info["ALLOWED_HOURS_3"].startswith("7;8")
    assert td.parse_userinfo("garbage\n\n# only comments") == {}


def test_issue3_time_left_uses_timekpr_value_not_limit_minus_usage():
    values = td.time_values_from_userinfo(td.parse_userinfo(USERINFO_LOGGED_OUT))
    assert values["time_remaining"] == 9600  # 2h40, the penalty is counted
    assert values["time_remaining"] != 14400 - 1200  # the old, wrong 3h40
    assert values["time_spent_today"] == 1200
    assert values["time_spent_week"] == 1200


def test_live_values_win_when_user_logged_in():
    values = td.time_values_from_userinfo(td.parse_userinfo(USERINFO_LOGGED_IN))
    assert values["time_remaining"] == 9000
    assert values["time_spent_today"] == 1800


def test_saved_time_left_is_capped_by_week_budget():
    info = td.parse_userinfo(USERINFO_LOGGED_OUT)
    info["LIMIT_PER_WEEK"] = "36000"
    info["TIME_SPENT_WEEK"] = "30000"
    assert td.time_values_from_userinfo(info)["time_remaining"] == 6000


def test_negative_or_missing_time_left():
    assert td.time_values_from_userinfo({"ACTUAL_TIME_LEFT_DAY": "-30"})[
        "time_remaining"
    ] == 0
    # No time-left field at all: let the caller fall back.
    assert "time_remaining" not in td.time_values_from_userinfo(
        {"TIME_SPENT_DAY": "60"}
    )


# ── Config file ────────────────────────────────────────────────────


def test_limits_are_positional_on_allowed_days():
    # Wednesday disabled: Timekpr's 5th value belongs to Saturday, not Friday.
    raw = {
        "ALLOWED_WEEKDAYS": "1;2;4;5;6;7",
        "LIMITS_PER_WEEKDAYS": "3600;3600;5400;5400;7200;9000",
        "LIMIT_PER_WEEK": "604800",
        "LIMIT_PER_MONTH": "2678400",
    }
    data = td.process_config(raw, previous_daily=[60, 60, 45, 60, 60, 60, 60])
    assert data["allowed_days"] == [1, 2, 4, 5, 6, 7]
    assert data["daily_limits"] == [60, 60, 45, 90, 90, 120, 150]
    assert data["weekly_limit"] == 168
    assert data["monthly_limit"] == 744


def test_all_days_allowed_is_unchanged_behaviour():
    raw = {"ALLOWED_WEEKDAYS": "1;2;3;4;5;6;7",
           "LIMITS_PER_WEEKDAYS": "3600;3600;3600;3600;3600;7200;7200"}
    assert td.process_config(raw)["daily_limits"] == [60] * 5 + [120, 120]


def test_empty_allowed_weekdays_means_no_day_allowed():
    assert td.parse_allowed_days({"ALLOWED_WEEKDAYS": ""}) == []
    assert td.parse_allowed_days({}) == [1, 2, 3, 4, 5, 6, 7]
    assert td.parse_allowed_days({"ALLOWED_WEEKDAYS": "7;1;9;x"}) == [1, 7]


@pytest.mark.parametrize(
    "days",
    [[1, 2, 3, 4, 5, 6, 7], [1, 2, 4, 5, 6, 7], [6, 7], [3], []],
)
def test_align_limits_roundtrip(days):
    daily = [10, 20, 30, 40, 50, 60, 70]
    sent = td.align_limits_for_timekpr(daily, days)
    assert len(sent) == 7  # '=' of --settimeleft indexes it by weekday
    raw = {
        "ALLOWED_WEEKDAYS": ";".join(map(str, days)),
        "LIMITS_PER_WEEKDAYS": ";".join(str(m * 60) for m in sent),
    }
    read_back = td.daily_limits_from_config(raw, days, previous=daily)
    assert read_back == daily
    if days == [1, 2, 3, 4, 5, 6, 7]:
        assert sent == daily


def test_is_valid_config():
    assert not td.is_valid_config(None)
    assert not td.is_valid_config({})
    assert not td.is_valid_config({"FOO": "1"})
    assert td.is_valid_config({"LIMITS_PER_WEEKDAYS": "3600"})


def test_hour_entries():
    assert td.parse_hour_entries("7[30-59];8;!9;20[00-45]") == [
        (7, 30, 59), (8, 0, 59), (9, 0, 59), (20, 0, 45)
    ]


@pytest.mark.parametrize(
    ("hs", "he", "ms", "me", "ok"),
    [
        (8, 20, 0, 59, True),
        (9, 21, 0, 0, True),     # "until 21:00"
        (21, 20, 0, 59, False),  # inverted
        (8, 8, 30, 10, False),   # inverted minutes
        (8, 8, 0, 0, False),     # empty
        (8, 8, 0, 59, True),
        (24, 25, 0, 0, False),
    ],
)
def test_valid_hour_range(hs, he, ms, me, ok):
    assert td.valid_hour_range(hs, he, ms, me) is ok


# ── Control file fallback ──────────────────────────────────────────

CONFIG = {
    "allowed_days": [1, 2, 3, 4, 5, 6, 7],
    "daily_limits": [240] * 7,
    "weekly_limit": 168,
    "monthly_limit": 744,
}
WEDNESDAY = date(2026, 10, 14)


def test_control_file_uses_balance_with_adjustments():
    raw = {
        "TIME_SPENT_BALANCE": "4800",
        "TIME_SPENT_DAY": "1200",
        "TIME_SPENT_WEEK": "1200",
        "TIME_SPENT_MONTH": "1200",
        "LAST_CHECKED": "2026-10-14 15:02:11",
    }
    values = td.time_values_from_control(raw, CONFIG, WEDNESDAY)
    assert values == {
        "time_spent_today": 1200,
        "time_spent_week": 1200,
        "time_remaining": 9600,
    }


def test_control_file_saved_yesterday_is_reset():
    raw = {
        "TIME_SPENT_BALANCE": "14400",
        "TIME_SPENT_DAY": "14400",
        "TIME_SPENT_WEEK": "50000",
        "TIME_SPENT_MONTH": "50000",
        "LAST_CHECKED": "2026-10-11 22:00:00",  # Sunday, previous ISO week
    }
    values = td.time_values_from_control(raw, CONFIG, date(2026, 10, 12))
    assert values["time_spent_today"] == 0
    assert values["time_spent_week"] == 0
    assert values["time_remaining"] == 14400


def test_control_file_disallowed_day_and_legacy_keys():
    config = dict(CONFIG, allowed_days=[1, 2, 4, 5, 6, 7])
    values = td.time_values_from_control(
        {"TIME_SPENT_DAY": "0"}, config, WEDNESDAY
    )
    assert values["time_remaining"] == 0
    # Old files without balance: fall back on the raw usage.
    values = td.time_values_from_control({"SECONDS_SPENT": "600"}, CONFIG, WEDNESDAY)
    assert values == {"time_spent_today": 600, "time_remaining": 14400 - 600}


def test_roll_over_stale_time_after_midnight_offline():
    data = dict(
        CONFIG,
        time_spent_today=5000,
        time_spent_week=9000,
        time_remaining=10,
        time_date="2026-10-13",
    )
    td.roll_over_stale_time(data, WEDNESDAY)
    assert data["time_spent_today"] == 0
    assert data["time_spent_week"] == 9000  # same ISO week
    assert data["time_remaining"] == 14400
    assert data["time_date"] == "2026-10-14"
    before = dict(data)
    td.roll_over_stale_time(data, WEDNESDAY)  # same day: untouched
    assert data == before
