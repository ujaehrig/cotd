"""Tests for user_matcher.py - fuzzy matching calendar events to users."""

import pytest
from user_matcher import UserMatcher


@pytest.fixture
def matcher():
    return UserMatcher(threshold=80)


@pytest.fixture
def users():
    return [
        (1, "john.doe@example.com", "John Doe"),
        (2, "victoria.smith@example.com", "Vicka"),
        (3, "rachana.patel@example.com", None),
    ]


class TestExtractNames:
    def test_removes_vacation_keywords(self, matcher):
        assert matcher.extract_names("Vacation John Doe") == ["john doe"]

    def test_removes_ooo_keyword(self, matcher):
        assert matcher.extract_names("OOO: Jane") == ["jane"]

    def test_removes_urlaub_keyword(self, matcher):
        assert matcher.extract_names("Rachana - Urlaub") == ["rachana"]

    def test_removes_pto_keyword(self, matcher):
        assert matcher.extract_names("PTO Jane Smith") == ["jane smith"]

    def test_removes_out_of_office(self, matcher):
        assert matcher.extract_names("Out of office Victoria") == ["victoria"]

    def test_removes_special_characters(self, matcher):
        assert matcher.extract_names("John - Doe") == ["john doe"]

    def test_empty_after_cleanup(self, matcher):
        assert matcher.extract_names("Vacation") == []

    def test_empty_string(self, matcher):
        assert matcher.extract_names("") == []

    def test_multiple_keywords(self, matcher):
        result = matcher.extract_names("OOO Vacation John")
        assert result == ["john"]


class TestMatchUser:
    def test_match_by_display_name(self, matcher, users):
        assert matcher.match_user("Vacation John Doe", users) == 1

    def test_match_by_nickname(self, matcher, users):
        assert matcher.match_user("OOO: Vicka", users) == 2

    def test_match_by_email_name(self, matcher, users):
        assert matcher.match_user("Rachana - Urlaub", users) == 3

    def test_no_match_returns_none(self, matcher, users):
        assert matcher.match_user("Unknown Person", users) is None

    def test_empty_title_returns_none(self, matcher, users):
        assert matcher.match_user("Vacation", users) is None

    def test_match_by_partial_name(self, matcher, users):
        # "Victoria" should match user 2 via email name part
        result = matcher.match_user("Out of office Victoria", users)
        assert result == 2

    def test_threshold_respected(self, users):
        strict = UserMatcher(threshold=100)
        # Partial match shouldn't pass strict threshold
        assert strict.match_user("Jon", users) is None

    def test_empty_users_list(self, matcher):
        assert matcher.match_user("Vacation John", []) is None

    def test_default_threshold_from_env(self, monkeypatch):
        monkeypatch.setenv("FUZZY_MATCH_THRESHOLD", "90")
        m = UserMatcher()
        assert m.threshold == 90

    def test_default_threshold_without_env(self, monkeypatch):
        monkeypatch.delenv("FUZZY_MATCH_THRESHOLD", raising=False)
        m = UserMatcher()
        assert m.threshold == 80
