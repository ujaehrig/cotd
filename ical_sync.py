#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "icalendar>=7.0.0",
#    "requests>=2.25.0",
#    "python-dotenv>=1.0.0",
# ]
# ///

"""
iCal parser module for fetching and parsing ICS calendar feeds.
"""

import os
import logging
import requests
from datetime import datetime, date
from typing import List, Dict, Optional
from urllib.parse import urlsplit, urlunsplit
from icalendar import Calendar
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ICalParser:
    """Fetches and parses iCal/ICS calendar feeds."""

    def __init__(self, timeout: int | None = None):
        """
        Initialize the iCal parser.

        Args:
            timeout: Request timeout in seconds. Defaults to ICAL_SYNC_TIMEOUT env var or 10.
        """
        if timeout is None:
            timeout = int(os.environ.get("ICAL_SYNC_TIMEOUT", "10"))
        self.timeout = timeout

    def fetch_calendar(self, url: str) -> Optional[Calendar]:
        """
        Fetch and parse iCal feed from URL.

        Args:
            url: URL to ICS feed

        Returns:
            Calendar object or None on error
        """
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return Calendar.from_ical(response.content)
        except Exception as e:
            parts = urlsplit(url)
            safe_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            logger.error(f"Error fetching calendar from {safe_url}: {e}")
            return None

    def extract_events(self, calendar: Calendar, start_date: date | None = None) -> List[Dict]:
        """
        Extract vacation events from calendar.

        Args:
            calendar: Calendar object
            start_date: Only include events on or after this date. Defaults to today.

        Returns:
            List of event dictionaries with keys: title, start_date, end_date, uid
        """
        if start_date is None:
            start_date = date.today()

        events = []
        for component in calendar.walk():
            if component.name != "VEVENT":
                continue

            try:
                # For Confluence calendars, only process leave entries
                subcal_type = str(component.get("X-CONFLUENCE-SUBCALENDAR-TYPE", ""))
                if subcal_type and subcal_type.lower() != "leaves":
                    continue

                uid = str(component.get("uid", ""))

                # Prefer ATTENDEE CN as the person's name (Confluence sets this reliably)
                attendee = component.get("attendee")
                if attendee and hasattr(attendee, "params"):
                    title = attendee.params.get("CN", "")
                else:
                    title = ""

                # Fall back to SUMMARY if no CN found
                if not title:
                    title = str(component.get("summary", ""))

                # Handle start date
                dtstart = component.get("dtstart")
                if dtstart is None:
                    continue

                start = dtstart.dt
                if isinstance(start, datetime):
                    start = start.date()

                # Handle end date
                dtend = component.get("dtend")
                if dtend:
                    end = dtend.dt
                    if isinstance(end, datetime):
                        end = end.date()
                else:
                    end = start

                # Filter out past events
                if end < start_date:
                    continue

                events.append(
                    {"title": title, "start_date": start, "end_date": end, "uid": uid}
                )

            except Exception as e:
                logger.warning(f"Error parsing event: {e}")
                continue

        return events


if __name__ == "__main__":
    # Simple test with a public holiday calendar
    parser = ICalParser()

    # Test with a sample ICS URL (German holidays)
    test_url = "https://www.calendarlabs.com/ical-calendar/ics/76/US_Holidays.ics"

    cal = parser.fetch_calendar(test_url)
    if cal:
        events = parser.extract_events(cal)
        print(f"Found {len(events)} events")
        for event in events[:5]:  # Show first 5
            print(f"  {event['title']}: {event['start_date']} to {event['end_date']}")
    else:
        print("Failed to fetch calendar")
