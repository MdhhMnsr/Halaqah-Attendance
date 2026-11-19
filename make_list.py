"""Make one day's attendance list from a WhatsApp chat export.

    python make_list.py data/chat.txt 18/11/2026

Options:
    --phone-utc 8        timezone of the phone that exported the chat (Malaysia = 8)
    --readings FILE      reuse saved readings instead of calling Claude again
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from build_list import assemble, render, render_preview_html
from names import name_key
from parse_chat import parse_export
from posted_list import carry_forward, is_posted_list, parse_posted_list
from reader import ReadMessage, read_messages

MADINAH = timezone(timedelta(hours=3))
WINDOW_OPENS = "10:00"     # Madinah time; earlier messages are ignored
ON_TIME_UNTIL = "10:30"    # after this, "Late"
STOP_READING = "13:00"     # class is long over by now

HERE = Path(__file__).parent


def at(day: datetime, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def load_env_file() -> None:
    """Read ANTHROPIC_API_KEY=... from a .env file next to this script, if there is one."""
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


def main() -> None:
    load_env_file()
    parser = argparse.ArgumentParser()
    parser.add_argument("chat")
    parser.add_argument("date", help="dd/mm/yyyy, the class date in Madinah")
    parser.add_argument("--phone-utc", type=float, default=8)
    parser.add_argument("--readings")
    args = parser.parse_args()
    started = time.time()

    day = datetime.strptime(args.date, "%d/%m/%Y").replace(tzinfo=MADINAH)
    messages = parse_export(args.chat, args.phone_utc)
    for m in messages:
        m.time = m.time.astimezone(MADINAH)  # do all checking in Madinah time

    # 1. Yesterday's final posted list -> carried names, and the header/footer to reuse
    before_today = [m for m in messages if m.time < at(day, "00:00") and m.sender and is_posted_list(m.text)]
    if not before_today:
        raise SystemExit("No earlier posted list found in the export.")
    # The final list is the last one with ✅/❌ ticks. A later list without ticks is usually
    # next day's list posted early (only carried names), so it is skipped.
    def has_ticks(text: str) -> bool:
        pl = parse_posted_list(text)
        return any(e.status != "none" for e in pl.did_not_recite + pl.today)

    ticked = [m for m in before_today if has_ticks(m.text)]
    if ticked:
        final_msg = ticked[-1]
    else:
        final_msg = before_today[-1]
        print("WARNING: no list with ✅/❌ ticks found before today, so everyone on the last list is carried.")
    print(f"[carry-forward] from the list {final_msg.sender} posted at {final_msg.time:%d/%m %H:%M} Madinah")
    final = parse_posted_list(final_msg.text)
    carried = carry_forward(final)

    # Spellings from recent lists help Claude write names the way the group does
    known: dict[str, str] = {}
    for m in before_today[-20:]:
        pl = parse_posted_list(m.text)
        for e in pl.did_not_recite + pl.today + pl.late + pl.listeners + pl.new_students:
            known.setdefault(name_key(e.name), e.name)

    # 2. Messages in today's window (skip admins' posted lists and system lines)
    window = [
        m for m in messages
        if at(day, WINDOW_OPENS) <= m.time < at(day, STOP_READING)
        and m.sender and not is_posted_list(m.text)
        and m.text.strip() not in ("<Media omitted>", "This message was deleted")
    ]
    numbered = list(enumerate(window, 1))

    # 3. Claude reads the messages (or we reuse a saved reading)
    readings_file = Path(args.readings) if args.readings else HERE / "data" / f"readings-{day:%Y-%m-%d}.json"
    saved = json.loads(readings_file.read_text(encoding="utf-8")) if readings_file.exists() else {}
    if isinstance(saved, list):
        # A hand-written test file: a plain list, used as it is
        readings = [ReadMessage(**r) for r in saved]
        print(f"[test readings] {readings_file.name}")
    else:
        # Saved readings are keyed by the message itself, so a second export later the
        # same day only sends the NEW messages to Claude (cheaper, and nothing goes stale)
        def key(m):
            return f"{m.time:%H:%M}|{m.sender}|{m.text}"

        new = [(n, m) for n, m in numbered if key(m) not in saved]
        if new:
            fresh = read_messages([(n, m.sender, m.text) for n, m in new], carried, list(known.values()))
            by_number = {n: m for n, m in new}
            for r in fresh:
                if r.message_number in by_number:
                    saved[key(by_number[r.message_number])] = r.model_dump(exclude={"message_number"})
            readings_file.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[claude] read {len(new)} new messages, reused {len(numbered) - len(new)}")
        readings = [
            ReadMessage(message_number=n, **saved[key(m)]) for n, m in numbered if key(m) in saved
        ]

    # 4. Plain code puts the list together
    times = {n: m.time for n, m in numbered}
    result = assemble(carried, readings, times, at(day, ON_TIME_UNTIL))
    text = render(result, final, day)

    out_file = HERE / "output" / f"list-{day:%Y-%m-%d}.txt"
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text(text, encoding="utf-8")
    out_file.with_suffix(".html").write_text(render_preview_html(text), encoding="utf-8")
    print(text)
    print(f"\nSaved to {out_file}")

    # 5. Log the run: what a preparer saved, and what it cost
    log = HERE / "logs" / "runs.jsonl"
    log.parent.mkdir(exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "class_date": f"{day:%Y-%m-%d}",
            "messages_read": len(window),
            "carried": len(carried), "today": len(result.today), "late": len(result.late),
            "listeners": len(result.listeners), "new": len(result.new_students),
            "seconds": round(time.time() - started, 1),
        }) + "\n")


if __name__ == "__main__":
    main()
