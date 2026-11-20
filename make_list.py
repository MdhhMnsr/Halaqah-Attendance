"""Make one day's attendance list from a WhatsApp chat export.

    python make_list.py path/to/chat-export.zip 18/11/2026

Options:
    --phone-utc 8        timezone of the phone/laptop that made the export (Malaysia = 8)
    --readings FILE      reuse saved readings instead of calling Claude again

The web page (app.py) calls make_day_list() directly.
"""

import argparse
import json
import os
import time
from dataclasses import dataclass, field
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

# Class runs Sunday to Thursday; Friday and Saturday are off days.
# Python counts Monday=0 ... Sunday=6.
CLASS_DAYS = {6, 0, 1, 2, 3}

HERE = Path(__file__).parent


def at(day: datetime, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


def is_class_day(day: datetime) -> bool:
    return day.weekday() in CLASS_DAYS


def next_class_day(day: datetime) -> datetime:
    """The day itself if there is class, otherwise the next class day (Friday/Saturday -> Sunday)."""
    while not is_class_day(day):
        day += timedelta(days=1)
    return day


@dataclass
class DayResult:
    text: str                       # the finished list, ready to paste
    notes: list[str] = field(default_factory=list)   # what the tool did, for the preparer
    stats: dict = field(default_factory=dict)        # counts only, never names (safe to log)


def make_day_list(chat_path: str, day: datetime, phone_utc: float, saved: dict | list | None = None) -> DayResult:
    """Build the list for one class day.

    saved: Claude's earlier readings. A dict keyed by message is updated in place, so a
    second run the same day only sends new messages. A list is a hand-written test file.
    None means read everything fresh (the web page).
    """
    started = time.time()
    notes: list[str] = []
    if not is_class_day(day):
        # Still allowed (handy for testing), but the preparer should know
        notes.append(f"NOTE: {day:%A %d/%m} is an off day (class runs Sunday to Thursday). "
                     f"The next class is {next_class_day(day):%A %d/%m}.")
    messages = parse_export(chat_path, phone_utc)
    for m in messages:
        m.time = m.time.astimezone(MADINAH)  # do all checking in Madinah time

    # 1. The last class day's final posted list -> carried names
    #    (on Sunday that is Thursday's list: off days have no list, so nothing special is needed)
    before_today = [m for m in messages if m.time < at(day, "00:00") and m.sender and is_posted_list(m.text)]
    if not before_today:
        raise ValueError("No list from an earlier day was found in this export. Export more days of the chat.")

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
        notes.append("WARNING: no list with ✅/❌ ticks was found before today, so everyone on the last list is carried.")
    notes.append(f"Carried names come from the list posted at {final_msg.time:%d/%m %H:%M} Madinah time.")
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
    if not window:
        notes.append("No messages after 10:00 Madinah time on this day yet; only the carried names are listed.")

    # 3. Claude reads the messages (or saved readings are reused)
    if isinstance(saved, list):
        readings = [ReadMessage(**r) for r in saved]
        sent_to_claude = 0
    else:
        saved = {} if saved is None else saved

        def key(m):
            return f"{m.time:%H:%M}|{m.sender}|{m.text}"

        new = [(n, m) for n, m in numbered if key(m) not in saved]
        if new:
            fresh = read_messages([(n, m.sender, m.text) for n, m in new], carried, list(known.values()))
            by_number = {n: m for n, m in new}
            for r in fresh:
                if r.message_number in by_number:
                    saved[key(by_number[r.message_number])] = r.model_dump(exclude={"message_number"})
        sent_to_claude = len(new)
        readings = [ReadMessage(message_number=n, **saved[key(m)]) for n, m in numbered if key(m) in saved]

    # 4. Plain code puts the list together
    times = {n: m.time for n, m in numbered}
    result = assemble(carried, readings, times, at(day, ON_TIME_UNTIL))
    text = render(result, day)

    stats = {
        "class_date": f"{day:%Y-%m-%d}",
        "messages_read": len(window), "sent_to_claude": sent_to_claude,
        "carried": len(carried), "present_carried": len(result.present_carried),
        "today": len(result.today), "late": len(result.late),
        "listeners": len(result.listeners), "new": len(result.new_students),
        "seconds": round(time.time() - started, 1),
    }
    return DayResult(text=text, notes=notes, stats=stats)


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

    day = datetime.strptime(args.date, "%d/%m/%Y").replace(tzinfo=MADINAH)
    readings_file = Path(args.readings) if args.readings else HERE / "data" / f"readings-{day:%Y-%m-%d}.json"
    saved = json.loads(readings_file.read_text(encoding="utf-8")) if readings_file.exists() else {}

    result = make_day_list(args.chat, day, args.phone_utc, saved)
    if isinstance(saved, dict) and result.stats["sent_to_claude"]:
        readings_file.parent.mkdir(exist_ok=True)
        readings_file.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")

    for note in result.notes:
        print(note)
    print(f"[claude] read {result.stats['sent_to_claude']} new messages")

    out_file = HERE / "output" / f"list-{day:%Y-%m-%d}.txt"
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text(result.text, encoding="utf-8")
    out_file.with_suffix(".html").write_text(render_preview_html(result.text), encoding="utf-8")
    print(result.text)
    print(f"\nSaved to {out_file}")

    # Log the run: counts only
    log = HERE / "logs" / "runs.jsonl"
    log.parent.mkdir(exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "source": "cli", **result.stats}) + "\n")


if __name__ == "__main__":
    main()
