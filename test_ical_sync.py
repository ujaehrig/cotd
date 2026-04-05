"""Tests for ical_sync.py - iCal calendar fetching and parsing."""

import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from icalendar import Calendar, Event
from ical_sync import ICalParser


@pytest.fixture
def parser():
    return ICalParser(timeout=5)


def _make_calendar(*events_data):
    """Helper to build a Calendar with VEVENT components."""
    cal = Calendar()
    for ev in events_data:
        event = Event()
        event.add("summary", ev["summary"])
        event.add("dtstart", ev["start"])
        event.add("dtend", ev["end"])
        if "uid" in ev:
            event.add("uid", ev["uid"])
        if "subcal_type" in ev:
            event["X-CONFLUENCE-SUBCALENDAR-TYPE"] = ev["subcal_type"]
        if "attendee_cn" in ev:
            from icalendar import vCalAddress

            attendee = vCalAddress(f"mailto:{ev.get('attendee_email', 'a@b.com')}")
            attendee.params["CN"] = ev["attendee_cn"]
            event.add("attendee", attendee)
        cal.add_component(event)
    return cal


class TestICalParserInit:
    def test_default_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("ICAL_SYNC_TIMEOUT", "15")
        p = ICalParser()
        assert p.timeout == 15

    def test_default_timeout_without_env(self, monkeypatch):
        monkeypatch.delenv("ICAL_SYNC_TIMEOUT", raising=False)
        p = ICalParser()
        assert p.timeout == 10

    def test_explicit_timeout(self):
        p = ICalParser(timeout=30)
        assert p.timeout == 30


class TestFetchCalendar:
    @patch("ical_sync.requests.get")
    def test_success(self, mock_get, parser):
        cal = Calendar()
        mock_resp = MagicMock()
        mock_resp.content = cal.to_ical()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = parser.fetch_calendar("https://example.com/cal.ics")
        assert result is not None
        mock_get.assert_called_once_with("https://example.com/cal.ics", timeout=5)

    @patch("ical_sync.requests.get")
    def test_network_error_returns_none(self, mock_get, parser):
        mock_get.side_effect = Exception("Connection refused")
        assert parser.fetch_calendar("https://bad.url") is None

    @patch("ical_sync.requests.get")
    def test_http_error_returns_none(self, mock_get, parser):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404")
        mock_get.return_value = mock_resp
        assert parser.fetch_calendar("https://example.com/missing.ics") is None


class TestExtractEvents:
    def test_basic_event(self, parser):
        cal = _make_calendar(
            {"summary": "Vacation John", "start": date(2026, 7, 1), "end": date(2026, 7, 5), "uid": "ev1"}
        )
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert len(events) == 1
        assert events[0]["title"] == "Vacation John"
        assert events[0]["start_date"] == date(2026, 7, 1)
        assert events[0]["end_date"] == date(2026, 7, 5)

    def test_filters_past_events(self, parser):
        cal = _make_calendar(
            {"summary": "Old vacation", "start": date(2020, 1, 1), "end": date(2020, 1, 5)}
        )
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert len(events) == 0

    def test_datetime_converted_to_date(self, parser):
        cal = _make_calendar(
            {"summary": "Meeting", "start": datetime(2026, 8, 1, 9, 0), "end": datetime(2026, 8, 1, 17, 0), "uid": "dt1"}
        )
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert events[0]["start_date"] == date(2026, 8, 1)
        assert events[0]["end_date"] == date(2026, 8, 1)

    def test_event_without_dtend_uses_start(self, parser):
        cal = Calendar()
        event = Event()
        event.add("summary", "Single day")
        event.add("dtstart", date(2026, 9, 1))
        event.add("uid", "single1")
        cal.add_component(event)

        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert len(events) == 1
        assert events[0]["end_date"] == date(2026, 9, 1)

    def test_confluence_leaves_type_included(self, parser):
        cal = _make_calendar(
            {"summary": "Leave John", "start": date(2026, 7, 1), "end": date(2026, 7, 5), "subcal_type": "leaves"}
        )
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert len(events) == 1

    def test_confluence_non_leaves_type_excluded(self, parser):
        cal = _make_calendar(
            {"summary": "Sprint Planning", "start": date(2026, 7, 1), "end": date(2026, 7, 5), "subcal_type": "events"}
        )
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert len(events) == 0

    def test_attendee_cn_preferred_over_summary(self, parser):
        cal = _make_calendar(
            {
                "summary": "Leave",
                "start": date(2026, 7, 1),
                "end": date(2026, 7, 5),
                "attendee_cn": "Jane Smith",
                "attendee_email": "jane@example.com",
            }
        )
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert events[0]["title"] == "Jane Smith"

    def test_empty_calendar(self, parser):
        cal = Calendar()
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert events == []

    def test_multiple_events(self, parser):
        cal = _make_calendar(
            {"summary": "Vacation A", "start": date(2026, 7, 1), "end": date(2026, 7, 5)},
            {"summary": "Vacation B", "start": date(2026, 8, 1), "end": date(2026, 8, 5)},
        )
        events = parser.extract_events(cal, start_date=date(2026, 1, 1))
        assert len(events) == 2
