import pandas as pd
import pytest

from ircc_times.analysis import check_feed, people_per_month, quebec_pairs, queue_age


def running_total(*steps):
    """One program's months, oldest first: months since applied 30, 20, 6 and 1."""
    return pd.DataFrame({
        "code": ["x"] * 4,
        "months_since_applied": [30, 20, 6, 1],
        "people_ahead": pd.Series(steps).cumsum().astype(float),
    })


def test_queue_age_reads_people_ahead_as_a_running_total():
    months = running_total(100, 200, 300, 400)  # running total: 100, 300, 600, 1000
    age = queue_age(months).loc["x"]
    assert age["over 2 years"] == 100
    assert age["1 to 2 years"] == 200
    assert age["1 year or less"] == 700
    assert age.sum() == 1000


def test_people_per_month_are_the_steps():
    assert people_per_month(running_total(100, 200, 300, 400)).tolist() == [100, 200, 300, 400]


def test_check_feed_rejects_a_falling_running_total():
    months = running_total(100, 200, 300, 400)
    months.loc[3, "people_ahead"] = 50  # falls in the newest month
    programs = pd.DataFrame({"code": ["x"], "people_waiting": [50.0],
                             "wait_months": [12.0], "wait_qualifier": ["about"]})
    with pytest.raises(ValueError, match="falls"):
        check_feed(programs, months)


def test_check_feed_rejects_a_total_that_disagrees():
    programs = pd.DataFrame({"code": ["x"], "people_waiting": [999.0],
                             "wait_months": [12.0], "wait_qualifier": ["about"]})
    with pytest.raises(ValueError, match="newest month"):
        check_feed(programs, running_total(100, 200, 300, 400))


def test_check_feed_rejects_a_floor_below_an_ordinary_estimate():
    # A "more than 2 years" floor under an "about 3 years" estimate can't be ranked.
    programs = pd.DataFrame({"code": ["x", "y"], "people_waiting": [1000.0, 1000.0],
                             "wait_months": [24.0, 36.0], "wait_qualifier": ["more than", "about"]})
    months = pd.concat([running_total(100, 200, 300, 400),
                        running_total(100, 200, 300, 400).assign(code="y")], ignore_index=True)
    with pytest.raises(ValueError, match="floor"):
        check_feed(programs, months)


def test_quebec_pairs_handle_floors():
    programs = pd.DataFrame({
        "program": ["A", "A", "B", "B", "C", "C"],
        "destination": ["Quebec", "outside Quebec"] * 3,
        "wait_months": [65.0, 30.0, 120.0, 14.0, 120.0, 120.0],
        "wait_qualifier": ["about", "about", "more than", "about", "more than", "more than"],
    })
    pairs = quebec_pairs(programs)
    assert pairs.loc["A", "difference"] == 35
    assert pairs.loc["B", "longer"] == "Quebec"  # one floor still shows which side is longer
    assert pd.isna(pairs.loc["C", "difference"])  # floors on both sides can't be compared
    assert pairs.loc["C", "longer"] == "Can't tell"
