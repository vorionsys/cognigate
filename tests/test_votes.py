"""
Tests for the file-backed theme voting system.

Tests vote casting, counting, retrieval, and file persistence.
"""

import json
import os
import tempfile

import pytest

# Override the votes file path before importing
_test_dir = tempfile.mkdtemp()
os.environ["COGNIGATE_VOTES_PATH"] = os.path.join(_test_dir, "test_votes.json")

from app.core.votes import cast_vote, get_vote_counts, get_all_votes, get_votes_for_theme


@pytest.fixture(autouse=True)
def clean_votes_file():
    """Reset votes file before each test."""
    path = os.environ["COGNIGATE_VOTES_PATH"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"votes": []}, f)
    yield
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


class TestCastVote:
    """Test vote casting."""

    def test_cast_vote_returns_record(self):
        record = cast_vote("dark_mode")
        assert record["theme_id"] == "dark_mode"
        assert record["voter"] == "anonymous"
        assert "timestamp" in record
        assert "ts_iso" in record

    def test_cast_vote_with_voter_name(self):
        record = cast_vote("cyberpunk", voter="Racas")
        assert record["voter"] == "Racas"

    def test_cast_vote_trims_whitespace(self):
        record = cast_vote("neon", voter="  spaces  ")
        assert record["voter"] == "spaces"

    def test_empty_voter_becomes_anonymous(self):
        record = cast_vote("minimal", voter="   ")
        assert record["voter"] == "anonymous"

    def test_multiple_votes_for_same_theme(self):
        cast_vote("retro")
        cast_vote("retro")
        cast_vote("retro")
        counts = get_vote_counts()
        assert counts["retro"] == 3


class TestGetVoteCounts:
    """Test vote counting."""

    def test_empty_counts(self):
        counts = get_vote_counts()
        assert counts == {}

    def test_counts_per_theme(self):
        cast_vote("dark")
        cast_vote("dark")
        cast_vote("light")
        counts = get_vote_counts()
        assert counts["dark"] == 2
        assert counts["light"] == 1

    def test_counts_multiple_themes(self):
        for theme in ["a", "b", "c", "a", "b", "a"]:
            cast_vote(theme)
        counts = get_vote_counts()
        assert counts["a"] == 3
        assert counts["b"] == 2
        assert counts["c"] == 1


class TestGetAllVotes:
    """Test retrieving all votes."""

    def test_empty_votes(self):
        votes = get_all_votes()
        assert votes == []

    def test_all_votes_returned(self):
        cast_vote("theme_1")
        cast_vote("theme_2")
        votes = get_all_votes()
        assert len(votes) == 2

    def test_votes_have_correct_fields(self):
        cast_vote("test_theme", voter="tester")
        votes = get_all_votes()
        assert len(votes) == 1
        vote = votes[0]
        assert vote["theme_id"] == "test_theme"
        assert vote["voter"] == "tester"
        assert "timestamp" in vote


class TestGetVotesForTheme:
    """Test filtering votes by theme."""

    def test_filter_by_theme(self):
        cast_vote("alpha")
        cast_vote("beta")
        cast_vote("alpha")
        results = get_votes_for_theme("alpha")
        assert len(results) == 2
        assert all(v["theme_id"] == "alpha" for v in results)

    def test_no_votes_for_theme(self):
        cast_vote("other")
        results = get_votes_for_theme("nonexistent")
        assert results == []
