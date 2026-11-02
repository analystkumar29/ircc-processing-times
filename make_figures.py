"""Rebuild every chart in figures/ and print the headline numbers quoted in the README.

Run from anywhere:  python make_figures.py
It does the same calculations as analysis.ipynb, using the same functions.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ircc_times import analysis, figures, load

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data" / "raw" / "flpt-en-2026-07-22.json"
OUTPUT = ROOT / "figures"


def main() -> None:
    feed = load.load_feed(SNAPSHOT)
    programs, months = load.programs_table(feed), load.months_table(feed)
    analysis.check_feed(programs, months)

    age = analysis.queue_age(months)
    across = analysis.queue_vs_wait(programs)
    pairs = analysis.quebec_pairs(programs)
    mix = analysis.answer_mix(months)

    figures.apply_style()
    labels = programs.set_index("code")["label"]
    charts = {
        "1_published_waits.png": figures.published_waits(programs),
        "2_queue_age.png": figures.queue_age_chart(age, labels, load.last_updated(feed)),
        "3_queue_vs_wait.png": figures.queue_vs_wait_chart(
            programs, across.statistic, across.pvalue),
        "4_quebec_vs_outside.png": figures.quebec_chart(pairs),
        "5_answer_mix.png": figures.answer_mix_chart(mix),
    }
    OUTPUT.mkdir(exist_ok=True)
    for name, fig in charts.items():
        fig.savefig(OUTPUT / name, dpi=150)
        plt.close(fig)
    print(f"Saved {len(charts)} charts to {OUTPUT}\n")

    # The headline numbers quoted in the README, so anyone can check them.
    # analysis.ipynb shows these and the supporting detail.
    waits = programs.set_index("label")["wait_months"].sort_values()
    floors = programs.loc[programs["wait_qualifier"] == analysis.FLOOR, "label"]
    print("Q1  shortest:", waits.index[0], waits.iloc[0], "months | median:", waits.median(),
          "| two years or more:", (waits >= 24).sum(), "of", len(waits))
    print("    more than 10 years:", ", ".join(sorted(floors)))

    over_1y = age["over 2 years"] + age["1 to 2 years"]
    total = age.to_numpy().sum()
    print(f"Q2  people waiting: {total:,.0f} | applied more than 1 year ago: {over_1y.sum():,.0f}"
          f" ({over_1y.sum() / total:.1%}) | more than 2 years: {age['over 2 years'].sum():,.0f}"
          f" ({age['over 2 years'].sum() / total:.1%})")
    share = (over_1y / age.sum(axis=1)).rename(index=labels).sort_values()
    print(f"    programs where most applied over a year ago: {(share > 0.5).sum()} of {len(share)}")
    extremes = pd.concat([share.head(2), share.tail(2)])
    print("    lowest and highest shares:",
          ", ".join(f"{name} {value:.1%}" for name, value in extremes.items()))

    exact = programs[programs["wait_qualifier"] != analysis.FLOOR]
    without_floors = analysis.queue_vs_wait(exact)
    within = analysis.within_program_rho(months)
    pace = (programs["people_waiting"] / programs["wait_months"]).set_axis(programs["label"])
    print(f"Q3  across programs: rho {across.statistic:.3f}, p {across.pvalue:.3f} | "
          f"without floors: rho {without_floors.statistic:.3f}, p {without_floors.pvalue:.3f}")
    print(f"    within programs: median rho {within.median():.3f}, lowest {within.min():.3f}"
          f" ({within.idxmin()})")
    print(f"    implied people per month: {pace.idxmin()} {pace.min():,.0f} ... "
          f"{pace.idxmax()} {pace.max():,.0f}")

    print("Q4  published wait in months, Quebec against outside Quebec:")
    print(pairs[["quebec", "outside", "difference", "longer"]].to_string())

    print("Data  what the tool tells people who already applied:")
    print(mix.join((mix / mix.sum() * 100).round(1).add_prefix("% ")).to_string())


if __name__ == "__main__":
    main()
