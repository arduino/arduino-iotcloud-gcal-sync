import gcalwatch


def test_extract_calendar_id():
    uri = "https://www.googleapis.com/calendar/v3/calendars/abc%40resource.calendar.google.com/events?alt=json"
    assert gcalwatch.extract_calendar_id(uri) == "abc@resource.calendar.google.com"
