#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#    "rapidfuzz>=3.0.0",
# ]
# ///

"""
User matching module for fuzzy matching calendar event names to users.
"""

import os
import re
from typing import Optional, List, Tuple
from rapidfuzz import fuzz, process


class UserMatcher:
    """Matches names from calendar events to users using fuzzy matching."""

    def __init__(self, threshold: int = None):
        """
        Initialize the user matcher.

        Args:
            threshold: Minimum similarity score (0-100) for a match.
                      Defaults to FUZZY_MATCH_THRESHOLD env var or 80.
        """
        if threshold is None:
            threshold = int(os.environ.get("FUZZY_MATCH_THRESHOLD", "80"))
        self.threshold = threshold

    def extract_names(self, event_title: str) -> List[str]:
        """
        Extract potential names from event title.

        Args:
            event_title: Calendar event title

        Returns:
            List of potential name strings
        """
        # Remove common vacation keywords
        keywords = [
            "vacation", "holiday", "ooo", "out of office", "pto", "off", "away",
            "urlaub", "abwesend", "frei"
        ]

        cleaned = event_title.lower()
        for keyword in keywords:
            cleaned = re.sub(rf'\b{keyword}\b', '', cleaned, flags=re.IGNORECASE)

        # Remove special characters and extra whitespace
        cleaned = re.sub(r'[:\-_/]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Return the cleaned string as potential name
        return [cleaned] if cleaned else []

    def match_user(
        self,
        event_title: str,
        users: List[Tuple[int, str, Optional[str]]]
    ) -> Optional[int]:
        """
        Match event title to a user.

        Args:
            event_title: Calendar event title
            users: List of (user_id, email, display_name) tuples

        Returns:
            user_id if match found, None otherwise
        """
        names = self.extract_names(event_title)
        if not names:
            return None

        # Build search candidates from users
        candidates = []
        for user_id, email, display_name in users:
            # Extract name from email (before @)
            email_name = email.split('@')[0].replace('.', ' ').replace('_', ' ')
            candidates.append((user_id, email_name))

            # Also add first and last name separately
            parts = email_name.split()
            for part in parts:
                if len(part) > 2:  # Skip very short parts
                    candidates.append((user_id, part))

            # Add display name if available
            if display_name:
                candidates.append((user_id, display_name))
                # Add display name parts
                display_parts = display_name.split()
                for part in display_parts:
                    if len(part) > 2:
                        candidates.append((user_id, part))

        # Try to match each extracted name
        for name in names:
            # Find best match
            best_match = None
            best_score = 0

            for user_id, candidate in candidates:
                score = fuzz.ratio(name.lower(), candidate.lower())
                if score > best_score:
                    best_score = score
                    best_match = user_id

            if best_score >= self.threshold:
                return best_match

        return None


if __name__ == "__main__":
    # Simple test
    matcher = UserMatcher(threshold=80)

    test_users = [
        (1, "john.doe@example.com", "John Doe"),
        (2, "victoria.smith@example.com", "Vicka"),
        (3, "rachana.patel@example.com", None),
    ]

    test_cases = [
        "Vacation John Doe",
        "OOO: Vicka",
        "Rachana - Urlaub",
        "Out of office - Victoria",
    ]

    for title in test_cases:
        user_id = matcher.match_user(title, test_users)
        print(f"'{title}' -> User ID: {user_id}")
