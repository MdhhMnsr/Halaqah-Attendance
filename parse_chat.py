"""Turn a WhatsApp chat export (.txt, or the .zip WhatsApp makes) into a list of messages.

Two export formats are read:
    18/11/2026, 15:02 - Admin A: some text          (Android phone)
    [11/18/26, 3:02:15 PM] Admin A: some text       (WhatsApp Desktop / iPhone)
A message can carry on over the next lines until the next dated line.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Android export: a new message starts with "dd/mm/yyyy, HH:MM - "
LINE_START = re.compile(r"^(\d{2}/\d{2}/\d{4}), (\d{1,2}:\d{2}) - (.*)$")

# iPhone / desktop export: "[11/19/26, 3:25:48 PM] Name: text" (month first, 12-hour clock)
BRACKET_START = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}(?::\d{2})?)[\s ]*([AP]M)\] (.*)$"
)


def _match_line(line: str) -> tuple[datetime, str] | None:
    """If the line starts a new message, return (time, rest of line)."""
    m = LINE_START.match(line)
    if m:
        date_part, time_part, rest = m.groups()
        return datetime.strptime(f"{date_part} {time_part}", "%d/%m/%Y %H:%M"), rest
    m = BRACKET_START.match(line)
    if m:
        date_part, time_part, ampm, rest = m.groups()
        year_fmt = "%Y" if len(date_part.split("/")[-1]) == 4 else "%y"
        sec_fmt = ":%S" if time_part.count(":") == 2 else ""
        when = datetime.strptime(f"{date_part} {time_part} {ampm}", f"%m/%d/{year_fmt} %I:%M{sec_fmt} %p")
        return when.replace(second=0), rest
    return None

# Invisible direction marks WhatsApp adds around Arabic text
INVISIBLE = "‎‏‪‫‬"


@dataclass
class Message:
    time: datetime  # timezone-aware, in the phone's timezone
    sender: str     # "" for system lines like "X was added"
    text: str


def _read_lines(path: str) -> list[str]:
    """Read the chat text from a .txt file, or straight from the .zip WhatsApp makes."""
    if path.lower().endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(path) as z:
            txt = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not txt:
                raise SystemExit(f"No .txt chat file inside {path}")
            return z.read(txt[0]).decode("utf-8").splitlines(keepends=True)
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def parse_export(path: str, phone_utc_offset_hours: float) -> list[Message]:
    """Read the export. The times in it are in the exporting phone's timezone."""
    tz = timezone(timedelta(hours=phone_utc_offset_hours))
    messages: list[Message] = []

    for raw in _read_lines(path):
        line = raw.rstrip("\r\n").lstrip(INVISIBLE)
        found = _match_line(line)
        if found:
            when, rest = found
            # "Name: text" for people; no ": " for system lines
            sender, sep, text = rest.partition(": ")
            if not sep:
                sender, text = "", rest
            messages.append(Message(when.replace(tzinfo=tz), sender.strip(), text))
        elif messages:
            # A continuation line of the previous message
            messages[-1].text += "\n" + line

    return messages
