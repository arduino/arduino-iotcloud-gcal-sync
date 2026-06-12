from datetime import datetime, timezone, timedelta

from gcalclient import GCalClient
from roomstatus import RoomStatus


def _client():
    return GCalClient("cal-id", "test_room")


def test_parse_event_dt_timed():
    c = _client()
    dt = c.parse_event_dt("2026-06-12T10:30:00+02:00")
    assert dt.year == 2026 and dt.hour == 10 and dt.minute == 30
    assert dt.tzinfo is not None


def test_parse_event_dt_all_day():
    #regression: all-day events carry a date-only value and must not raise
    c = _client()
    dt = c.parse_event_dt("2026-06-12")
    assert dt.year == 2026 and dt.month == 6 and dt.day == 12
    assert dt.tzinfo == timezone.utc


def test_status_busy_for_ongoing_event():
    c = _client()
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
    end = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S%z")
    events = [{
        "id": "ev1",
        "summary": "Standup",
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }]
    result = c.get_calendar_status_from_events(events)
    assert result.is_valid()
    assert result.busynow == RoomStatus.BUSY
    assert result.curevmsg == "Standup"


def test_status_free_for_future_event():
    c = _client()
    now = datetime.now(timezone.utc)
    start = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S%z")
    end = (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S%z")
    events = [{
        "id": "ev2",
        "summary": "Later meeting",
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }]
    result = c.get_calendar_status_from_events(events)
    assert result.is_valid()
    assert result.busynow == RoomStatus.FREE
    assert result.nextevmsg == "Later meeting"


def test_status_all_day_event_does_not_crash():
    #regression for the all-day parsing bug
    c = _client()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    events = [{
        "id": "allday",
        "summary": "Maintenance",
        "start": {"date": today},
        "end": {"date": tomorrow},
    }]
    result = c.get_calendar_status_from_events(events)
    assert result.is_valid()


def test_empty_events_valid_free():
    c = _client()
    result = c.get_calendar_status_from_events([])
    assert result.is_valid()
