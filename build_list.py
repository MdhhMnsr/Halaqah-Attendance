"""Put the list together from the carried names and Claude's readings. Plain code, no AI."""

from dataclasses import dataclass, field
from datetime import datetime

from names import name_key
from posted_list import PostedList
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


def render(day: DayList, template: PostedList, date: datetime) -> str:
    """Write the list in the same layout the group already uses."""
    header_lines = []
    for line in template.header.split("\n"):
        if line.startswith("🕋"):
            line = f"🕋 {date:%d/%m/%Y}"
        elif line.startswith("🗓"):
            line = f"🗓️ {ARABIC_DAYS[date.weekday()]}"
        header_lines.append(line)

    out = header_lines + ["", "💠 *من لم يقرأنَّ* 💠", ""]
    for i, name in enumerate(day.carried, 1):
        mark = " (موجودة)" if name in day.present_carried else ""
        out.append(f"{i}. {name}{mark}")

    out += ["", "🎀🌷القائمة الحضور 🌷🎀"]
    number = 0
    for name in day.today:
        number += 1
        out.append(f"{str(number).translate(ARABIC_DIGITS)}- {name}")

    out += ["", "⏰⏰⏰⏰⏰⏰⏰⏰"]
    for name in day.late:
        number += 1
        out.append(f"{str(number).translate(ARABIC_DIGITS)}- {name}")

    out += ["", "🎧 المستمعات 🎧", *day.listeners]
    out += ["", "🎀 طالبة جديدة 🎀", *day.new_students]
    if template.footer:
        out += ["", template.footer]

    # A line that starts with a number, emoji or English name would show left-to-right.
    # An invisible right-to-left mark at the start of each line makes every line RTL in WhatsApp.
    RLM = "‏"
    return "\n".join(RLM + line if line else line for line in "\n".join(out).split("\n"))


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
