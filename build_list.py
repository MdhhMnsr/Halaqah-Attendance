"""Put the list together from the carried names and Claude's readings. Plain code, no AI."""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from hijridate import Gregorian

from names import name_key
from reader import ReadMessage

ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
ARABIC_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


@dataclass
class DayList:
    carried: list[str]
    present_carried: set[str] = field(default_factory=set)
    today: list[str] = field(default_factory=list)
    late: list[str] = field(default_factory=list)
    listeners: list[str] = field(default_factory=list)
    new_students: list[str] = field(default_factory=list)
    _seen: set[str] = field(default_factory=set)

    def _first_time(self, name: str) -> bool:
        """True the first time we see this sister today; stops duplicates."""
        key = name_key(name)
        if not key or key in self._seen:
            return False
        self._seen.add(key)
        return True


def assemble(
    carried: list[str],
    readings: list[ReadMessage],
    message_times: dict[int, datetime],   # message number -> time in Madinah
    on_time_until: datetime,
) -> DayList:
    day = DayList(carried=carried)
    carried_by_key = {name_key(n): n for n in carried}

    for reading in sorted(readings, key=lambda r: r.message_number):
        name = reading.name_arabic.strip()
        if reading.kind in ("not_attendance", "apology_absent") or not name:
            continue

        # Is she on the carried list? Trust Claude's match, then check the spelling too.
        carried_name = reading.carried_name if reading.carried_name in carried else ""
        carried_name = carried_name or carried_by_key.get(name_key(name), "")

        # Only someone coming to recite is marked present; a listener goes under Listeners
        if carried_name and reading.kind == "attending":
            # Rule: a carried sister who checks in today stays up in "did not recite"
            day.present_carried.add(carried_name)
            day._seen.add(name_key(carried_name))
            day._seen.add(name_key(name))
            continue

        if not day._first_time(name):
            continue  # already listed today (sent twice, or corrected her message)

        if reading.kind == "listener":
            day.listeners.append(name)
        elif reading.kind == "new_student":
            day.new_students.append(name)
        elif message_times[reading.message_number] <= on_time_until:
            day.today.append(name)
        else:
            day.late.append(name)

    return day


HIJRI_MONTHS = ["محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة",
                "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة"]
TEMPLATE_FILE = Path(__file__).parent / "list_template.txt"


def hijri_date(date: datetime) -> str:
    """The Islamic (Umm al-Qura) date, written like the admins do: 8 جمادى الآخرة 1448 هـ"""
    h = Gregorian(date.year, date.month, date.day).to_hijri()
    return f"{h.day} {HIJRI_MONTHS[h.month - 1]} {h.year} هـ"


def render(day: DayList, date: datetime) -> str:
    """Fill the group's list template (list_template.txt) for the class date."""
    numbered = [f"{i}. {name}{' (موجودة)' if name in day.present_carried else ''}"
                for i, name in enumerate(day.carried, 1)]
    today = [f"{str(i).translate(ARABIC_DIGITS)}- {name}" for i, name in enumerate(day.today, 1)]
    late = [f"{str(i).translate(ARABIC_DIGITS)}- {name}"           # numbering carries on from Today
            for i, name in enumerate(day.late, len(day.today) + 1)]

    text = TEMPLATE_FILE.read_text(encoding="utf-8").strip()
    for placeholder, value in {
        "[HIJRI_DATE]": hijri_date(date),
        "[DAY]": ARABIC_DAYS[date.weekday()],
        "[TEACHER]": os.environ.get("TEACHER_NAME", "المعلمة"),   # kept out of the public code
        "[DID_NOT_RECITE]": "\n".join(numbered),
        "[TODAY]": "\n".join(today),
        "[LATE]": "\n".join(late),
        "[LISTENERS]": "\n".join(day.listeners),
        "[NEW_STUDENTS]": "\n".join(day.new_students),
    }.items():
        text = text.replace(placeholder, value)

    # A line that starts with a number, emoji or English name would show left-to-right.
    # An invisible right-to-left mark at the start of each line makes every line RTL in WhatsApp.
    RLM = "‏"
    return "\n".join(RLM + line if line else line for line in text.split("\n"))


def render_preview_html(list_text: str) -> str:
    """The same list in a right-to-left page, to check how it looks before posting."""
    import html
    return (
        '<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8">'
        "<title>Attendance list preview</title>"
        '<body style="font:18px/1.7 Tahoma,Arial,sans-serif;max-width:480px;margin:24px auto;'
        'padding:16px;background:#e5ddd5"><div style="background:#fff;border-radius:8px;padding:12px 16px;'
        'white-space:pre-wrap">' + html.escape(list_text) + "</div></body></html>"
    )
