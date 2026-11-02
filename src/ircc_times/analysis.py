"""The calculations behind each question. The notebook and make_figures.py both use these."""

import numpy as np
import pandas as pd
from scipy import stats

FLOOR = "more than"  # IRCC's "More than 10 years": the real wait is longer
TIME_GIVEN = ["none", "about"]  # qualifiers of an ordinary "N months left"

# What the tool tells someone who already applied, grouped for counting.
ANSWERS = {
    "none": "Time left given",
    "about": "Time left given",
    "more than": "More than 10 years",
    "need more time": "We need more time to process your application",
    "no data": "No data available",
}
ANSWER_ORDER = list(dict.fromkeys(ANSWERS.values()))  # unique, in the order above


def check_feed(programs: pd.DataFrame, months: pd.DataFrame) -> None:
    """Stop early if the feed breaks an assumption the analysis relies on."""
    # 1. "People ahead" must never fall as the application month gets later,
    #    otherwise it can't be read as a running total.
    rising = months.groupby("code")["people_ahead"].apply(lambda s: s.is_monotonic_increasing)
    if not rising.all():
        raise ValueError(f"'people ahead' falls over time in: {sorted(rising.index[~rising])}")

    # 2. In the newest month, the running total should reach everyone waiting.
    newest = months.groupby("code")["people_ahead"].last()
    waiting = programs.set_index("code")["people_waiting"].reindex(newest.index)
    if not newest.equals(waiting):
        raise ValueError("'people ahead' in the newest month differs from total people waiting")

    # 3. Every "more than 10 years" floor must be above every ordinary estimate.
    #    Then floors can still be ranked (they are the longest), and medians and
    #    rank correlations stay correct even though their real values are unknown.
    floor = programs["wait_qualifier"] == FLOOR
    if programs.loc[~floor, "wait_months"].max() >= programs.loc[floor, "wait_months"].min():
        raise ValueError("a 'more than' floor overlaps ordinary estimates, so ranks are unsafe")


def queue_age(months: pd.DataFrame) -> pd.DataFrame:
    """People waiting in each program, split by how long ago they applied.

    For an application month, "people ahead of you" counts everyone still waiting
    who applied in that month or earlier: a running total (check_feed confirms it
    never falls). So its largest value among months more than a year old is the
    number of people who applied more than a year ago.
    """
    total = months.groupby("code")["people_ahead"].max()

    def applied_more_than(months_ago: int) -> pd.Series:
        older = months[months["months_since_applied"] > months_ago]
        return older.groupby("code")["people_ahead"].max().reindex(total.index, fill_value=0)

    over_1y, over_2y = applied_more_than(12), applied_more_than(24)
    return pd.DataFrame({
        "over 2 years": over_2y,
        "1 to 2 years": over_1y - over_2y,
        "1 year or less": total - over_1y,
    })


def people_per_month(months: pd.DataFrame) -> pd.Series:
    """People still waiting who applied in each month: the step in the running total.

    Expects rows in months_table order (each program oldest month first).
    The feed gives each total in hundreds, and small ones as "Less than 100",
    which is read as 100. So one month's figure is rough, but a sum over
    neighbouring months is close because the steps add back up to the totals.
    """
    steps = months.groupby("code")["people_ahead"].diff()
    return steps.fillna(months["people_ahead"])  # a program's first month is its own step


def answer_mix(months: pd.DataFrame) -> pd.DataFrame:
    """Month rows and people waiting, by what the tool says about time left."""
    answer = months["months_left_qualifier"].map(ANSWERS).rename("answer")
    mix = pd.DataFrame({
        "rows": answer.value_counts(),
        "people": people_per_month(months).groupby(answer).sum(),
    })
    return mix.reindex(ANSWER_ORDER).fillna(0)


def queue_vs_wait(programs: pd.DataFrame):
    """Spearman rank correlation between queue size and published wait, across programs.

    Ranks suit this data: a "more than 10 years" floor can't be measured, but it
    can be ranked, because check_feed confirms it is above every other estimate.
    Returns scipy's result, with .statistic (rho) and .pvalue.
    """
    return stats.spearmanr(programs["people_waiting"], programs["wait_months"])


def within_program_rho(months: pd.DataFrame) -> pd.Series:
    """Spearman correlation between people ahead and months left, inside each program."""
    timed = months[months["months_left_qualifier"].isin(TIME_GIVEN)]
    return timed.groupby("code")[["people_ahead", "months_left"]].apply(
        lambda g: stats.spearmanr(g["people_ahead"], g["months_left"]).statistic
    )


def quebec_pairs(programs: pd.DataFrame) -> pd.DataFrame:
    """Programs split by Quebec / outside Quebec, side by side, largest gap first."""
    split = programs.dropna(subset=["destination"])
    # pivot (not pivot_table) on purpose: a duplicated program raises an error
    # instead of being silently averaged.
    waits = split.pivot(index="program", columns="destination", values="wait_months")
    floors = split.pivot(index="program", columns="destination", values="wait_qualifier") == FLOOR
    pairs = pd.DataFrame({
        "quebec": waits["Quebec"],
        "outside": waits["outside Quebec"],
        "quebec_floor": floors["Quebec"],
        "outside_floor": floors["outside Quebec"],
    })
    # A floor on one side still shows which side is longer (check_feed confirms a
    # floor is above every ordinary estimate); the gap is then a minimum. With a
    # floor on both sides nothing can be said, so the gap is left empty.
    both = pairs["quebec_floor"] & pairs["outside_floor"]
    pairs["difference"] = (pairs["quebec"] - pairs["outside"]).mask(both)
    pairs["longer"] = np.select(
        [both, pairs["difference"] > 0, pairs["difference"] < 0],
        ["Can't tell", "Quebec", "Outside Quebec"],
        default="Same",
    )
    return pairs.sort_values("difference", ascending=False)
