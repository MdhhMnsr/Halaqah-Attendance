"""Turn the run logs into a monthly usage table for the README (counts only, no names).

    python usage_table.py                         print the table
    python usage_table.py --update-readme         also write it into README.md
    python usage_table.py --minutes-saved 15      add an hours-saved column (once measured)
    python usage_table.py --extra space-logs.txt  include web-page runs copied from the Space logs

Only real runs count: a run on a class day (Sunday to Thursday), made on that same day in
Madinah time, on or after the trial start, that read at least one attendance message.
Test runs (the sample chat, lists built ahead of time, off days) are left out. When a day
was run more than once, the run that read the most messages stands for that day.
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from make_list import CLASS_DAYS, MADINAH

HERE = Path(__file__).parent
TRIAL_START = date(2026, 11, 19)
START, END = "<!-- usage-table-start -->", "<!-- usage-table-end -->"


def read_runs(paths: list[Path]) -> list[dict]:
    runs = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line[line.find("{"):] if "{" in line else ""   # Space log lines may have a prefix
            try:
                run = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "class_date" in run and "ran_at" in run:
                runs.append(run)
    return runs


def is_real_run(run: dict) -> bool:
    class_day = date.fromisoformat(run["class_date"])
    ran_on = datetime.fromisoformat(run["ran_at"]).astimezone(MADINAH).date()
    return (class_day >= TRIAL_START
            and class_day.weekday() in CLASS_DAYS
            and ran_on == class_day
            and run.get("messages_read", 0) > 0)


def build_table(runs: list[dict], minutes_saved: float | None) -> str:
    real = [r for r in runs if is_real_run(r)]
    best_run = {}
    for r in real:
        if r["messages_read"] >= best_run.get(r["class_date"], {}).get("messages_read", -1):
            best_run[r["class_date"]] = r

    months = defaultdict(lambda: {"days": 0, "messages": 0, "names": 0, "web": 0})
    for day, r in best_run.items():
        m = months[day[:7]]
        m["days"] += 1
        m["messages"] += r["messages_read"]
        m["names"] += sum(r.get(k, 0) for k in ("carried", "today", "late", "listeners", "new"))
        m["web"] += r.get("source") == "web"

    header = "| Month | Class days with a list | Attendance messages read | Names placed | From the web page |"
    rule = "|---|---|---|---|---|"
    if minutes_saved:
        header += " Hours saved (est.) |"
        rule += "---|"
    rows = []
    for month in sorted(months):
        m = months[month]
        label = datetime.strptime(month, "%Y-%m").strftime("%b %Y")
        row = f"| {label} | {m['days']} | {m['messages']} | {m['names']} | {m['web']} |"
        if minutes_saved:
            row += f" {m['days'] * minutes_saved / 60:.1f} |"
        rows.append(row)
    if not rows:
        rows.append("| (no real runs yet) | | | | |")

    note = (f"\n\n*Counted from the tool's run logs (counts only). Real runs only: a class day, run on "
            f"that day, from {TRIAL_START:%d %B %Y}. Updated {datetime.now(MADINAH):%d %B %Y}.*")
    if minutes_saved:
        note += f" *Hours saved assume {minutes_saved:g} minutes saved per class day.*"
    return "\n".join([header, rule, *rows]) + note


def update_readme(table: str) -> None:
    readme = HERE / "README.md"
    text = readme.read_text(encoding="utf-8")
    block = f"{START}\n{table}\n{END}"
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    else:
        raise SystemExit(f"README.md has no {START} ... {END} markers to replace.")
    readme.write_text(text, encoding="utf-8")
    print("README.md updated.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-readme", action="store_true")
    parser.add_argument("--minutes-saved", type=float)
    parser.add_argument("--extra", nargs="*", default=[], help="more log files, e.g. copied Space logs")
    args = parser.parse_args()

    runs = read_runs([HERE / "logs" / "runs.jsonl", *map(Path, args.extra)])
    table = build_table(runs, args.minutes_saved)
    print(table)
    if args.update_readme:
        update_readme(table)


if __name__ == "__main__":
    main()
