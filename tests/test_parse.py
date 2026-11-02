import math

import pytest

from ircc_times.parse import DAYS_PER_MONTH, parse_duration, parse_people


@pytest.mark.parametrize(
    "text, months, qualifier",
    [
        ("About 26 months", 26, "about"),
        ("11 months", 11, "none"),
        ("2 months left", 2, "none"),
        ("About 1 month left", 1, "about"),  # singular "month"
        ("More than 10 years", 120, "more than"),  # years become months; the value is a floor
        ("  about   26 MONTHS ", 26, "about"),  # spacing and capitals don't matter
    ],
)
def test_reads_every_duration_format_in_the_feed(text, months, qualifier):
    assert parse_duration(text) == (months, qualifier)


def test_weeks_and_days_convert_to_months_through_days():
    weeks, _ = parse_duration("3 weeks")
    assert weeks * DAYS_PER_MONTH == pytest.approx(21)  # 3 weeks is exactly 21 days
    days, _ = parse_duration("45 days")
    assert days == pytest.approx(45 / 30.4375)


def test_month_and_year_follow_the_average_calendar_month():
    # The documented convention: 1 month = 365.25 / 12 = 30.4375 days.
    assert parse_duration("1 month")[0] * DAYS_PER_MONTH == pytest.approx(30.4375)
    assert parse_duration("1 year")[0] * DAYS_PER_MONTH == pytest.approx(365.25)
    assert parse_duration("1 year")[0] == parse_duration("12 months")[0]


@pytest.mark.parametrize(
    "text, qualifier",
    [
        ("We need more time to process your application", "need more time"),
        ("No data available", "no data"),
    ],
)
def test_messages_become_missing_not_zero(text, qualifier):
    months, found = parse_duration(text)
    assert math.isnan(months)
    assert found == qualifier


@pytest.mark.parametrize(
    "text", ["", "26", "About months", "Soon", "26 fortnights", "About -3 months", "1.5 months"]
)
def test_unrecognised_duration_raises_instead_of_guessing(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize(
    "text, count, qualifier",
    [
        ("About 12,300 people waiting", 12_300, "about"),
        ("About 1,374,100 people ahead of you", 1_374_100, "about"),
        ("Less than 100 people ahead of you", 100, "less than"),  # 100 is a ceiling
    ],
)
def test_reads_people_counts(text, count, qualifier):
    assert parse_people(text) == (count, qualifier)


@pytest.mark.parametrize("text", ["About 26 months", "No data available", "About 12,300 people"])
def test_people_parser_rejects_other_text(text):
    with pytest.raises(ValueError):
        parse_people(text)
