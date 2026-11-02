import math
from pathlib import Path

import pandas as pd
import pytest

from ircc_times.load import describe_program, load_feed, months_table, programs_table

SNAPSHOT = Path(__file__).parents[1] / "data" / "raw" / "flpt-en-2026-07-22.json"

# A miniature feed with the same shape as the real one.
TINY_FEED = {
    "default-update": {"flpt_lastupdated": "July 7, 2026", "flpt_interval": "monthly"},
    "current-flpt": {"cec": "About 6 months", "pgp-quebec": "About 65 months"},
    "total-people": {"cec": "About 61,500 people waiting",
                     "pgp-quebec": "About 10,500 people waiting"},
    "wait-times": {
        "cec-2026/06": "5 months left",
        "cec-2025/06": "We need more time to process your application",
        "pgp-quebec-2026/06": "64 months left",
    },
    "people-ahead": {
        "cec-2026/06": "About 61,500 people ahead of you",
        "cec-2025/06": "Less than 100 people ahead of you",
        "pgp-quebec-2026/06": "About 10,500 people ahead of you",
    },
}


def test_describe_program_splits_the_quebec_suffix():
    assert describe_program("pgp-quebec") == {
        "program": "Parents and grandparents", "family": "Family",
        "destination": "Quebec", "label": "Parents and grandparents (Quebec)",
    }
    assert describe_program("pgp-roc")["destination"] == "outside Quebec"
    # A hyphen inside a code is not a destination.
    assert describe_program("startup-visa")["destination"] is None


def test_unknown_program_code_fails_loudly():
    with pytest.raises(KeyError):
        describe_program("brand-new-program")


def test_programs_table_has_one_numeric_row_per_program():
    table = programs_table(TINY_FEED).set_index("code")
    assert list(table.index) == ["cec", "pgp-quebec"]
    assert table.loc["pgp-quebec", "wait_months"] == 65
    assert table.loc["pgp-quebec", "people_waiting"] == 10_500
    assert table.loc["cec", "label"] == "Canadian Experience Class"


def test_months_table_splits_keys_sorts_and_counts_months():
    table = months_table(TINY_FEED)
    # Sorted by program, then oldest month first.
    assert list(zip(table["code"], table["applied"].dt.strftime("%Y-%m"), strict=True)) == [
        ("cec", "2025-06"), ("cec", "2026-06"), ("pgp-quebec", "2026-06")]
    old = table.iloc[0]
    assert old["months_since_applied"] == 13  # June 2025 to July 2026
    assert math.isnan(old["months_left"])
    assert old["months_left_qualifier"] == "need more time"
    assert (old["people_ahead"], old["people_ahead_qualifier"]) == (100, "less than")


def test_real_snapshot_parses_completely():
    feed = load_feed(SNAPSHOT)
    programs, months = programs_table(feed), months_table(feed)
    assert len(programs) == 28
    assert len(months) == 3_574
    assert programs["wait_months"].notna().all()
    assert months["people_ahead"].notna().all()
    assert pd.api.types.is_datetime64_any_dtype(months["applied"])
