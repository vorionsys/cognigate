# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Simple file-backed vote store for theme voting.

Stores votes as a JSON file. Each vote records:
- theme_id
- voter name (optional)
- timestamp
"""

import json
import os
import time
from pathlib import Path
from threading import Lock

_VOTES_FILE = Path(os.environ.get(
    "COGNIGATE_VOTES_PATH",
    Path(__file__).parent.parent.parent / "data" / "theme_votes.json"
))
_lock = Lock()


def _ensure_file() -> None:
    """Ensure the votes file and its parent directory exist."""
    _VOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _VOTES_FILE.exists():
        _VOTES_FILE.write_text(json.dumps({"votes": []}, indent=2))


def _read_votes() -> list[dict]:
    """Read all votes from file."""
    _ensure_file()
    data = json.loads(_VOTES_FILE.read_text())
    return data.get("votes", [])


def _write_votes(votes: list[dict]) -> None:
    """Write votes to file."""
    _ensure_file()
    _VOTES_FILE.write_text(json.dumps({"votes": votes}, indent=2))


def cast_vote(theme_id: str, voter: str = "anonymous") -> dict:
    """Cast a vote for a theme. Returns the new vote record."""
    with _lock:
        votes = _read_votes()
        record = {
            "theme_id": theme_id,
            "voter": voter.strip() or "anonymous",
            "timestamp": time.time(),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        votes.append(record)
        _write_votes(votes)
    return record


def get_vote_counts() -> dict[str, int]:
    """Get vote counts per theme."""
    votes = _read_votes()
    counts: dict[str, int] = {}
    for v in votes:
        tid = v["theme_id"]
        counts[tid] = counts.get(tid, 0) + 1
    return counts


def get_all_votes() -> list[dict]:
    """Get all vote records."""
    return _read_votes()


def get_votes_for_theme(theme_id: str) -> list[dict]:
    """Get all votes for a specific theme."""
    return [v for v in _read_votes() if v["theme_id"] == theme_id]
