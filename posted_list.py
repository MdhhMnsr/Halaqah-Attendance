"""Read a list the admins posted in the group, and work out tomorrow's carry-forward.

A posted list has these sections, in order:
    💠 من لم يقرأن 💠      did not recite yesterday (carried forward)
    🌷 القائمة الحضور 🌷   today's list
    ⏰⏰⏰⏰⏰⏰⏰⏰           late
    🎧 المستمعات 🎧        listeners
    🎀 طالبة جديدة 🎀      new students
    ■ ...                  footer note

After class each name gets ✅ (recited), ❌ (called, no answer) or nothing (not reached).
"""

import re
from dataclasses import dataclass

# Digits in all three forms used in the group: 123, ١٢٣ (Arabic), ۱۲۳ (Persian/Urdu)
DIGITS = "0-9٠-٩۰-۹"
NUMBERING = re.compile(rf"^[\s{DIGITS}]+[\s.\-–)]*")

# Anything after the name: marks, emojis, "(present)" notes
MARK_START = re.compile(r"[(（/✅❌🎀🎁🍊✔☑]|حاضر|موجود")


@dataclass
class Entry:
    name: str     # the name as written, marks removed
    status: str   # "recited" (✅), "crossed" (❌) or "none"


@dataclass
class PostedList:
    header: str                 # everything above "من لم يقرأن"
    did_not_recite: list[Entry]
    today: list[Entry]
    late: list[Entry]
    listeners: list[Entry]
    new_students: list[Entry]
    footer: str                 # the "■ ..." note at the bottom


def is_posted_list(text: str) -> bool:
    return "من لم" in text and "الحضور" in text


def _section_of(line: str) -> str | None:
    """Return the section a heading line starts, or None if it is not a heading."""
    if "من لم" in line:
        return "did_not_recite"
    if "الحضور" in line and ("قائم" in line or "القائمہ" in line):
        return "today"
    if "⏰⏰" in line:
        return "late"
    if "المستمع" in line or "🎧" in line:
        return "listeners"
    if "طالبة جديدة" in line or "طالبات جدد" in line:
        return "new_students"
    return None


def _entry_from(line: str) -> Entry | None:
    status = "recited" if "✅" in line else "crossed" if "❌" in line else "none"
    name = NUMBERING.sub("", line)
    cut = MARK_START.search(name)
    if cut:
        name = name[: cut.start()]
    name = name.strip(" *_\t.-")
    return Entry(name, status) if name else None


def parse_posted_list(text: str) -> PostedList:
    header_lines: list[str] = []
    footer_lines: list[str] = []
    sections: dict[str, list[Entry]] = {
        "did_not_recite": [], "today": [], "late": [], "listeners": [], "new_students": []
    }
    current: str | None = None

    for line in text.split("\n"):
        line = line.replace("<This message was edited>", "").rstrip()
        if line.lstrip().startswith("■") or footer_lines:
            footer_lines.append(line)
            continue
        heading = _section_of(line)
        if heading:
            current = heading
            continue
        if current is None:
            header_lines.append(line)
            continue
        entry = _entry_from(line)
        if entry:
            sections[current].append(entry)

    return PostedList(
        header="\n".join(header_lines).strip(),
        footer="\n".join(footer_lines).strip(),
        **sections,
    )


def carry_forward(final_list: PostedList) -> list[str]:
    """Names for tomorrow's "did not recite" section.

    Rules agreed with the group:
      - a name is carried forward only ONCE: anyone already in "did not recite"
        is dropped tomorrow, reached or not
      - from "today": ✅ recited -> dropped, ❌ crossed out -> dropped, no mark -> carried
      - late, listeners, new students -> never carried
    """
    from names import same_person  # local import keeps the modules independent

    carried: list[str] = []
    for entry in final_list.today:
        if entry.status != "none":
            continue
        if any(same_person(entry.name, already) for already in carried):
            continue  # the same sister written twice
        carried.append(entry.name)
    return carried
