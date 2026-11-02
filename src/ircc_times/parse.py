"""Turn IRCC's display text into numbers.

The feed stores every figure as the sentence shown on canada.ca, for example
"About 26 months", "More than 10 years", "2 months left" or "Less than 100
people ahead of you". Each parser returns (number, qualifier) so the words that
change what a number means ("more than" makes it a floor) stay next to it.
"""

import math
import re

# Durations are kept in months because that is the unit IRCC uses in this feed;
# turning "About 26 months" into days would invent precision. Years convert
# exactly. Days and weeks never appear in this feed, but IRCC's pages for visas
# and permits use them, so they are accepted using the average calendar month:
# 365.25 days / 12 = 30.4375 days.
DAYS_PER_MONTH = 365.25 / 12
MONTHS_PER_UNIT = {
    "day": 1 / DAYS_PER_MONTH,
    "week": 7 / DAYS_PER_MONTH,
    "month": 1,
    "year": 12,
}

# Sentences IRCC shows instead of a time. They become NaN, never 0: a zero would
# read as "no wait left" and pull averages down. The qualifier says which one it was.
MESSAGES = {
    "we need more time to process your application": "need more time",
    "no data available": "no data",
}

QUALIFIER = r"(?:(?P<qualifier>about|more than|less than) )?"
NUMBER = r"(?P<number>\d[\d,]*)"
DURATION = re.compile(QUALIFIER + NUMBER + r" (?P<unit>day|week|month|year)s?(?: left)?")
PEOPLE = re.compile(QUALIFIER + NUMBER + r" people (?:waiting|ahead of you)")


def _tidy(text: str) -> str:
    """Lower-case and collapse whitespace, so spacing or capitals never break a match."""
    return " ".join(text.split()).lower()


def _number(match: re.Match) -> float:
    return float(match["number"].replace(",", ""))


def parse_duration(text: str) -> tuple[float, str]:
    """Return (months, qualifier) for text such as "About 26 months".

    The qualifier is "about", "more than" (the real value is higher), "less than",
    "none" for a plain number, or the name of a message from MESSAGES. Anything
    else raises ValueError, so a change in IRCC's wording stops the analysis
    instead of quietly turning into missing values.
    """
    tidy = _tidy(text)
    if tidy in MESSAGES:
        return math.nan, MESSAGES[tidy]
    match = DURATION.fullmatch(tidy)
    if match is None:
        raise ValueError(f"Unrecognised duration: {text!r}")
    return _number(match) * MONTHS_PER_UNIT[match["unit"]], match["qualifier"] or "none"


def parse_people(text: str) -> tuple[float, str]:
    """Return (count, qualifier) for "About 12,300 people waiting" or
    "Less than 100 people ahead of you"."""
    match = PEOPLE.fullmatch(_tidy(text))
    if match is None:
        raise ValueError(f"Unrecognised people count: {text!r}")
    return _number(match), match["qualifier"] or "none"
