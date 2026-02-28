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
import requests
from datetime import datetime, date
from typing import List, Dict, Optional
from icalendar import Calendar
from dotenv import load_dotenv

load_dotenv()


class ICalParser:
    """Fetches and parses iCal/ICS calendar feeds."""

    def __init__(self, timeout: int = None):
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
            print(f"Error fetching calendar from {url}: {e}")
            return None

    def extract_events(
        self, 
        calendar: Calendar, 
        start_date: date = None
    ) -> List[Dict]:
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
                # Extract event data
                title = str(component.get('summary', ''))
                uid = str(component.get('uid', ''))
                
                # Handle start date
                dtstart = component.get('dtstart')
                if dtstart is None:
                    continue
                
                start = dtstart.dt
                if isinstance(start, datetime):
                    start = start.date()
                
                # Handle end date
                dtend = component.get('dtend')
                if dtend:
                    end = dtend.dt
                    if isinstance(end, datetime):
                        end = end.date()
                else:
                    # If no end date, assume single day
                    end = start

                # Filter out past events
                if end < start_date:
                    continue

                events.append({
                    'title': title,
                    'start_date': start,
                    'end_date': end,
                    'uid': uid
                })

            except Exception as e:
                print(f"Error parsing event: {e}")
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
