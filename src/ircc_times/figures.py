"""The charts in figures/. Each function takes tidy tables and returns a Figure.

Each title states the finding, and every number in a title or subtitle is
computed from the data passed in, so a chart can't drift from the analysis.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, PercentFormatter

from .analysis import FLOOR

SOURCE = ("Source: Immigration, Refugees and Citizenship Canada, 'Check processing times' "
          "data feed on canada.ca, updated July 7, 2026 (snapshot of July 22, 2026).")

# Colours come from a palette checked for colour-blind separation. Text always
# uses the greys, never a data colour.
INK, SECONDARY, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
BLUE, LIGHT_BLUE, DARK_BLUE, ORANGE = "#2a78d6", "#86b6ef", "#104281", "#eb6834"
BAR_HEIGHT = 0.62


def apply_style() -> None:
    """Quiet axes and a light grid, so the data is the loudest thing on each chart."""
    plt.rcParams.update({
        "font.size": 10,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": SECONDARY,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": AXIS,
        "ytick.color": AXIS,
        "xtick.labelcolor": SECONDARY,
        "ytick.labelcolor": INK,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def _frame(fig, title: str, subtitle: str, legend: tuple | None = None) -> None:
    """Add a header (title, subtitle, optional legend) and a source line.

    Positions are in inches from the top or bottom edge, so every chart gets the
    same header whatever its height. The plot is then fitted in the space left.
    """
    height = fig.get_figheight()
    header = 0.45 + 0.25 * (subtitle.count("\n") + 1)  # title + subtitle lines
    if legend is not None:
        handles, labels = legend
        fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.003, 1 - header / height),
                   ncols=len(handles), fontsize=9, handlelength=1.2, borderaxespad=0)
        header += 0.3
    bottom = 0.4  # room for the source line
    fig.get_layout_engine().set(rect=(0, bottom / height, 1, 1 - (header + bottom) / height))
    fig.text(0.01, 1 - 0.15 / height, title, fontsize=13.5, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 1 - 0.45 / height, subtitle, fontsize=10, color=SECONDARY, va="top",
             linespacing=1.5)
    fig.text(0.01, 0.12 / height, SOURCE, fontsize=7.5, color=MUTED, va="bottom")


def _horizontal_bars(ax, labels) -> np.ndarray:
    """Shared setup for charts with one row per program; returns the row positions."""
    rows = np.arange(len(labels))
    ax.set_yticks(rows, labels)
    ax.set_ylim(-0.6, len(labels) - 0.4)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    return rows


def published_waits(programs: pd.DataFrame):
    """Q1: the published wait for a new applicant, one bar per program."""
    # Rows are drawn bottom-up, so sort shortest first to put the longest on top.
    # Ties are sorted Z to A so they read A to Z from the top.
    data = programs.sort_values(["wait_months", "label"], ascending=[True, False])
    floor = (data["wait_qualifier"] == FLOOR).to_numpy()

    fig, ax = plt.subplots(figsize=(9, 9.5), layout="constrained")
    rows = _horizontal_bars(ax, data["label"])
    ax.barh(rows, data["wait_months"], height=BAR_HEIGHT, color=np.where(floor, LIGHT_BLUE, BLUE))
    values = zip(rows, data["wait_months"], data["wait_text"], floor, strict=True)
    for row, months, text, is_floor in values:
        ax.text(months + 1.5, row, text.lower() if is_floor else f"{months:.0f}",
                va="center", fontsize=8.5, color=SECONDARY)
    ax.set_xlim(0, 150)
    ax.set_xticks(range(0, 121, 12))
    ax.set_xlabel("Months")

    shortest, longest = data.iloc[0], data.iloc[-1]
    _frame(fig,
           f"Published waits run from {shortest['wait_months']:.0f} months to "
           f"{longest['wait_text'].lower()}",
           f"Estimated wait for someone applying now, {len(data)} programs. "
           f"The median program is {data['wait_months'].median():.0f} months.\n"
           "Pale bars are IRCC's 'more than 10 years': a floor, so the real wait is longer.")
    return fig


def queue_age_chart(age: pd.DataFrame, labels: pd.Series, updated: pd.Timestamp):
    """Q2: each program's queue split by how long ago people applied."""
    shares = age.div(age.sum(axis=1), axis=0)
    older = shares["over 2 years"] + shares["1 to 2 years"]
    order = shares.assign(older=older).sort_values(["older", "over 2 years"]).index
    shares = shares.loc[order]

    # Band names as dates: "more than a year" means applied before this month last year.
    month = updated.to_period("M").to_timestamp()
    one_year, two_years = month - pd.DateOffset(years=1), month - pd.DateOffset(years=2)
    names = {
        "over 2 years": f"Applied before {two_years:%B %Y}",
        "1 to 2 years": f"{two_years:%B %Y} to {one_year - pd.DateOffset(months=1):%B %Y}",
        "1 year or less": f"{one_year:%B %Y} or later",
    }

    fig, ax = plt.subplots(figsize=(9, 9.5), layout="constrained")
    rows = _horizontal_bars(ax, labels.reindex(shares.index))
    left = np.zeros(len(shares))
    for column, colour in zip(names, [DARK_BLUE, BLUE, LIGHT_BLUE], strict=True):
        # A thin white edge leaves a gap between touching segments.
        ax.barh(rows, shares[column], left=left, height=BAR_HEIGHT, color=colour,
                edgecolor="white", linewidth=1, label=names[column])
        left += shares[column].to_numpy()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlabel("Share of people waiting")

    total = age.to_numpy().sum()
    applied_over_1y = (age["over 2 years"] + age["1 to 2 years"]).sum()
    _frame(fig,
           f"In {(older > 0.5).sum()} of {len(age)} programs, most people waiting "
           "applied more than a year ago",
           f"Across all {len(age)} queues, {applied_over_1y / total:.0%} of about "
           f"{total / 1e6:.2f} million people applied before {one_year:%B %Y}.",
           legend=ax.get_legend_handles_labels())
    return fig


# Points named on the scatter, with text offsets in points (x, y), placed by eye.
SCATTER_LABELS = {
    "citizen-grants": (9, 0),
    "caregiver": (9, 0),
    "quebec-business": (9, 0),
    "pgp-quebec": (9, 0),
    "cec": (9, 0),
    "government-refugees-quebec": (9, 0),
}


def queue_vs_wait_chart(programs: pd.DataFrame, rho: float, pvalue: float):
    """Q3: queue size against published wait, one point per program."""
    floor = programs["wait_qualifier"] == FLOOR
    fig, ax = plt.subplots(figsize=(9, 6), layout="constrained")
    # A white ring round each point keeps overlapping points legible.
    point = {"edgecolor": "white", "linewidth": 1.5, "zorder": 3}
    ax.scatter(programs.loc[~floor, "people_waiting"], programs.loc[~floor, "wait_months"],
               s=64, color=BLUE, label="Published estimate", **point)
    ax.scatter(programs.loc[floor, "people_waiting"], programs.loc[floor, "wait_months"],
               s=90, marker="^", color=ORANGE,
               label="More than 10 years (drawn at 10 years; the real wait is longer)", **point)

    by_code = programs.set_index("code")
    for code, (dx, dy) in SCATTER_LABELS.items():
        row = by_code.loc[code]
        ax.annotate(row["label"], (row["people_waiting"], row["wait_months"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=8.5, color=SECONDARY,
                    va="center", ha="left" if dx >= 0 else "right")

    ax.set_xscale("log")
    ax.set_xlim(150, 2_000_000)  # extra room on the right for the labels
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_xlabel("People waiting (log scale)")
    ax.set_ylim(0, 128)
    ax.set_yticks(range(0, 121, 24))
    ax.set_ylabel("Published wait for a new applicant (months)")

    _frame(fig,
           "A bigger queue does not mean a longer wait",
           f"Each point is one of {len(programs)} programs. Spearman rank correlation "
           f"{rho:.2f} (p = {pvalue:.2f}).\nOne snapshot: this describes July 2026, "
           "it doesn't show cause and effect.",
           legend=ax.get_legend_handles_labels())
    return fig


def _gap_text(row: pd.Series) -> str:
    """'Quebec 35 months longer', with 'at least' when one side is a floor."""
    if row["longer"] == "Can't tell":
        return "Both more than 10 years"
    at_least = "at least " if row["quebec_floor"] or row["outside_floor"] else ""
    return f"{row['longer']} {at_least}{abs(row['difference']):.0f} months longer"


def quebec_chart(pairs: pd.DataFrame):
    """Q4: published wait inside and outside Quebec, one row per split program."""
    data = pairs.iloc[::-1]  # pairs arrive largest gap first; rows are drawn bottom-up
    fig, ax = plt.subplots(figsize=(9, 6.2), layout="constrained")
    rows = _horizontal_bars(ax, [f"{name}\n{_gap_text(row)}" for name, row in data.iterrows()])
    ax.tick_params(axis="y", labelsize=9)
    ends = data[["quebec", "outside"]]
    ax.hlines(rows, ends.min(axis=1), ends.max(axis=1), color=AXIS, linewidth=2, zorder=1)
    same = (data["quebec"] == data["outside"]).to_numpy()
    for side, colour, nudge in [("outside", ORANGE, -0.12), ("quebec", BLUE, 0.12)]:
        y = rows + np.where(same, nudge, 0)  # when both sides match, keep both markers visible
        floor = data[f"{side}_floor"].to_numpy()
        for marker, mask in [("o", ~floor), (">", floor)]:  # a triangle marks a floor
            ax.scatter(data.loc[mask, side], y[mask], s=80, marker=marker, color=colour,
                       edgecolor="white", linewidth=1.5, zorder=3)
    ax.set_xlim(0, 126)
    ax.set_xticks(range(0, 121, 12))
    ax.set_xlabel("Published wait for a new applicant (months)")
    key = [Line2D([], [], marker="o", linestyle="", color=BLUE, markersize=8, label="Quebec"),
           Line2D([], [], marker="o", linestyle="", color=ORANGE, markersize=8,
                  label="Outside Quebec"),
           Line2D([], [], marker=">", linestyle="", color=MUTED, markersize=8,
                  label="More than 10 years (a floor: the real wait is longer)")]

    comparable = pairs["longer"] != "Can't tell"
    _frame(fig,
           f"Quebec waits are longer in {(pairs['longer'] == 'Quebec').sum()} of the "
           f"{comparable.sum()} programs that can be compared",
           "Published wait for a new applicant, for the programs IRCC splits by "
           "where the applicant will live.",
           legend=(key, [line.get_label() for line in key]))
    return fig


def answer_mix_chart(mix: pd.DataFrame):
    """Data limits: what the tool says about time left, counted by rows and by people."""
    shares = mix / mix.sum()  # each column now sums to 1
    colours = [BLUE, LIGHT_BLUE, ORANGE, AXIS]  # time given, floor, message, no data
    bars = {"rows": f"Month rows in the feed\n({mix['rows'].sum():,.0f})",
            "people": f"People waiting\n(about {mix['people'].sum():,.0f})"}

    fig, ax = plt.subplots(figsize=(9, 3.9), layout="constrained")
    rows = _horizontal_bars(ax, list(bars.values())[::-1])  # rows on top
    for row, column in zip(rows[::-1], bars, strict=True):
        left = 0.0
        for (answer, share), colour in zip(shares[column].items(), colours, strict=True):
            ax.barh(row, share, left=left, height=0.55, color=colour, edgecolor="white",
                    linewidth=1, label=answer if column == "rows" else None)
            if share >= 0.06:  # only label segments wide enough to hold the text
                ax.text(left + share / 2, row, f"{share:.0%}", ha="center", va="center",
                        fontsize=9, color="white" if colour in (BLUE, ORANGE) else INK)
            left += share
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1))

    message = "We need more time to process your application"
    _frame(fig,
           f"'We need more time' fills {shares.loc[message, 'rows']:.0%} of the rows "
           f"but covers {shares.loc[message, 'people']:.0%} of people waiting",
           "What the tool tells people who already applied. Counting rows overstates the "
           "message:\nnearly all of its rows are application months over two years old, "
           "with 100 people or fewer in each.",
           legend=ax.get_legend_handles_labels())
    return fig
