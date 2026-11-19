"""Turn a WhatsApp chat export (.txt, or the .zip WhatsApp makes) into a list of messages.

WhatsApp writes dates and times the way the exporting phone is set up, for example:
    18/11/2026, 15:02 - Admin A: some text          (Android, day first, 24-hour)
    11/18/26, 3:02 PM - Admin A: some text          (Android, month first, 12-hour)
    [11/18/26, 3:02:15 PM] Admin A: some text       (WhatsApp Desktop / iPhone)
    [18.11.26, 15:02:15] Admin A: some text         (iPhone, Europe)
Whether the date is day/month or month/day is worked out from the whole file.
A message can carry on over the next lines until the next dated line.
"""

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Start of a message: [optional bracket] date, time [am/pm] then "] " or " - "
LINE_START = re.compile(
    r"^\[?(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{2,4}),?\s+"     # date, three numbers
    r"(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?"                  # time, seconds optional
    r"[\s ]*([aApP]\.?\s?[mM]\.?)?"                     # AM/PM, optional
    r"(?:\]\s*|\s+-\s+)(.*)$"                                # "] " or " - ", then the rest
)

# Invisible direction marks WhatsApp adds around Arabic text
INVISIBLE = "‎‏‪‫‬﻿"


@dataclass
class Message:
    time: datetime  # timezone-aware, in the phone's timezone
    sender: str     # "" for system lines like "X was added"
    text: str


def _read_lines(path: str) -> list[str]:
    """Read the chat text from a .txt file, or straight from the .zip WhatsApp makes."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            txt = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not txt:
                raise ValueError("There is no chat .txt file inside this zip.")
            return z.read(txt[0]).decode("utf-8-sig").splitlines()
    with open(path, encoding="utf-8-sig") as f:
        return f.read().splitlines()


def _date_order(matches: list[re.Match]) -> str:
    """'ymd', 'dmy' or 'mdy', decided from every date in the file."""
    if any(len(m.group(1)) == 4 for m in matches):
        return "ymd"
    if any(int(m.group(1)) > 12 for m in matches):
        return "dmy"
    if any(int(m.group(2)) > 12 for m in matches):
        return "mdy"
    # Can't tell (only days 1-12 in the file): US-style 12-hour exports are month first
    return "mdy" if any(m.group(7) for m in matches) else "dmy"


def _to_datetime(m: re.Match, order: str) -> datetime:
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year, month, day = {"ymd": (a, b, c), "dmy": (c, b, a), "mdy": (c, a, b)}[order]
    if year < 100:
        year += 2000
    hour, minute = int(m.group(4)), int(m.group(5))
    ampm = (m.group(7) or "").replace(".", "").replace(" ", "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return datetime(year, month, day, hour, minute)


def parse_export(path: str, phone_utc_offset_hours: float) -> list[Message]:
    """Read the export. The times in it are in the exporting phone's timezone."""
    tz = timezone(timedelta(hours=phone_utc_offset_hours))
    lines = [line.lstrip(INVISIBLE) for line in _read_lines(path)]
    matches = [LINE_START.match(line) for line in lines]
    order = _date_order([m for m in matches if m])

    messages: list[Message] = []
    for line, match in zip(lines, matches):
        if match:
            rest = match.group(8)
            # "Name: text" for people; no ": " for system lines
            sender, sep, text = rest.partition(": ")
            if not sep:
                sender, text = "", rest
            messages.append(Message(_to_datetime(match, order).replace(tzinfo=tz), sender.strip(), text))
        elif messages:
            # A continuation line of the previous message
            messages[-1].text += "\n" + line
    return messages
