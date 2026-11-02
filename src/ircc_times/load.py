"""Read IRCC's processing-times feed into two tidy tables.

The JSON has four sections:
  current-flpt  the estimated wait for someone applying now, per program
  total-people  how many people are waiting, per program
  wait-times    the time left for someone who applied in a given month
  people-ahead  how many people are ahead of that person in the queue
The last two share keys such as "pgp-roc-2025/07" (program code, then month).
"""

import json
from pathlib import Path

import pandas as pd

from .parse import parse_duration, parse_people

# Program code -> (readable name, family). Names follow IRCC's "Check processing
# times" tool. Codes ending in "-quebec" or "-roc" ("rest of Canada") are one
# program split by where the applicant will live.
PROGRAMS = {
    "aip": ("Atlantic Immigration Program", "Economic"),
    "caregiver": ("Caregivers", "Economic"),
    "cec": ("Canadian Experience Class", "Economic"),
    "fsw": ("Federal Skilled Worker", "Economic"),
    "pnp-ee": ("Provincial Nominee (Express Entry)", "Economic"),
    "pnp-base": ("Provincial Nominee (non-Express Entry)", "Economic"),
    "qsw": ("Quebec Skilled Worker", "Economic"),
    "quebec-business": ("Quebec Business Class", "Economic"),
    "self-employed": ("Self-employed persons", "Economic"),
    "startup-visa": ("Start-up Visa", "Economic"),
    "spousal-canada": ("Spouse or partner in Canada", "Family"),
    "spousal-abroad": ("Spouse or partner outside Canada", "Family"),
    "pgp": ("Parents and grandparents", "Family"),
    "government-refugees": ("Government-assisted refugees", "Refugees and humanitarian"),
    "private-refugees": ("Privately sponsored refugees", "Refugees and humanitarian"),
    "protected-persons-in-canada": ("Protected persons in Canada", "Refugees and humanitarian"),
    "dependants-abroad": ("Dependants of protected persons", "Refugees and humanitarian"),
    "humanitarian": ("Humanitarian and compassionate", "Refugees and humanitarian"),
    "citizen-grants": ("Citizenship grant", "Citizenship"),
    "citizen-proofs": ("Citizenship certificate", "Citizenship"),
}
DESTINATIONS = {"quebec": "Quebec", "roc": "outside Quebec"}


def load_feed(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def last_updated(feed: dict) -> pd.Timestamp:
    """The date IRCC says it last updated the estimates, e.g. "July 7, 2026"."""
    return pd.to_datetime(feed["default-update"]["flpt_lastupdated"], format="%B %d, %Y")


def describe_program(code: str) -> dict:
    """Turn a code such as "pgp-quebec" into a name, family, destination and chart label."""
    base, _, suffix = code.rpartition("-")
    if suffix in DESTINATIONS:
        name, family = PROGRAMS[base]
        destination = DESTINATIONS[suffix]
        return {"program": name, "family": family, "destination": destination,
                "label": f"{name} ({destination})"}
    # An unknown code raises KeyError here: better to stop than to chart a blank label.
    name, family = PROGRAMS[code]
    return {"program": name, "family": family, "destination": None, "label": name}


def programs_table(feed: dict) -> pd.DataFrame:
    """One row per program: the published wait for a new applicant and the queue size."""
    rows = []
    for code, wait_text in feed["current-flpt"].items():
        wait, wait_qualifier = parse_duration(wait_text)
        waiting, waiting_qualifier = parse_people(feed["total-people"][code])
        rows.append({
            "code": code,
            **describe_program(code),
            "wait_months": wait,
            "wait_qualifier": wait_qualifier,
            "wait_text": wait_text,
            "people_waiting": waiting,
            "people_waiting_qualifier": waiting_qualifier,
        })
    return pd.DataFrame(rows)


def months_table(feed: dict) -> pd.DataFrame:
    """One row per program and application month: time left and people ahead."""
    rows = []
    for key, left_text in feed["wait-times"].items():
        code, month = key.rsplit("-", 1)  # "pgp-roc-2025/07" -> "pgp-roc", "2025/07"
        months_left, left_qualifier = parse_duration(left_text)
        ahead, ahead_qualifier = parse_people(feed["people-ahead"][key])
        rows.append({
            "code": code,
            "applied": month,
            "months_left": months_left,
            "months_left_qualifier": left_qualifier,
            "months_left_text": left_text,
            "people_ahead": ahead,
            "people_ahead_qualifier": ahead_qualifier,
        })
    table = pd.DataFrame(rows)
    table["applied"] = pd.to_datetime(table["applied"], format="%Y/%m")  # 1st of that month

    # Whole calendar months from the application month to the month of IRCC's
    # update: applied June 2026, updated July 2026 -> 1.
    updated = last_updated(feed)
    table.insert(2, "months_since_applied",
                 (updated.year - table["applied"].dt.year) * 12
                 + (updated.month - table["applied"].dt.month))

    # Oldest to newest within each program: analysis.py reads "people ahead" as a
    # running total, which only works in this order.
    return table.sort_values(["code", "applied"], ignore_index=True)
