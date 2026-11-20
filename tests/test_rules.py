"""Tests for the plain-code rules, run on the made-up sample chat (no API key needed).

    python tests/test_rules.py      (or: pytest)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_list import assemble  # noqa: E402
from make_list import MADINAH, ON_TIME_UNTIL, STOP_READING, WINDOW_OPENS, at  # noqa: E402
from names import same_person  # noqa: E402
from parse_chat import parse_export  # noqa: E402
from posted_list import carry_forward, is_posted_list, parse_posted_list  # noqa: E402
from reader import ReadMessage  # noqa: E402

SAMPLE = str(ROOT / "samples" / "sample-chat.txt")
DAY2 = datetime(2026, 11, 3, tzinfo=MADINAH)


def load_sample():
    messages = parse_export(SAMPLE, phone_utc_offset_hours=8)
    for m in messages:
        m.time = m.time.astimezone(MADINAH)
    return messages


def test_same_person_ignores_spelling_variants():
    assert same_person("نسيمة حسن", "نسيمه حسن")
    assert same_person("نسيمة حسن", "نسیمہ حسن")      # Urdu keyboard
    assert same_person("أسماء", "اسماء")                 # hamza
    assert not same_person("سلمى", "سلمان")


def test_class_days_are_sunday_to_thursday():
    from make_list import is_class_day, next_class_day
    friday, saturday, sunday = (datetime(2026, 11, d, tzinfo=MADINAH) for d in (20, 21, 22))
    assert not is_class_day(friday) and not is_class_day(saturday)
    assert is_class_day(sunday) and is_class_day(datetime(2026, 11, 19, tzinfo=MADINAH))  # Thursday
    assert next_class_day(friday) == sunday and next_class_day(sunday) == sunday


def test_hijri_date_matches_the_admins_list():
    from build_list import hijri_date
    # The admins' own list for Wednesday 16/09/2026 said: 5 ربيع الآخر 1448 هـ
    assert hijri_date(datetime(2026, 9, 16)) == "5 ربيع الآخر 1448 هـ"


def test_parses_desktop_format_with_multiline_messages():
    messages = load_sample()
    assert len(messages) == 12                       # 1 list + 11 messages; the notice line is skipped
    card = next(m for m in messages if m.sender == "Salma S")
    assert "الاسم: سلمى" in card.text                # second and third lines kept
    assert card.time.strftime("%H:%M") == "10:00"    # 15:00 Malaysia = 10:00 Madinah


def test_carry_forward_rules():
    final = parse_posted_list(next(m.text for m in load_sample() if is_posted_list(m.text)))
    # Did-not-recite names are carried only once -> لينا and هدى are dropped.
    # ✅ dropped, "غدير left" dropped, سلمى written twice counts once, late (جنى) and listeners never carried.
    assert carry_forward(final) == ["سلمى", "آية"]


def test_whole_day_on_sample():
    messages = load_sample()
    final = parse_posted_list(next(m.text for m in messages if is_posted_list(m.text)))
    window = [
        m for m in messages
        if at(DAY2, WINDOW_OPENS) <= m.time < at(DAY2, STOP_READING) and not is_posted_list(m.text)
    ]
    assert window[0].sender == "Salma S"            # Rana at 9:59 is too early and ignored

    readings = [ReadMessage(**r) for r in json.loads((ROOT / "samples" / "sample-readings.json").read_text(encoding="utf-8"))]
    times = {n: m.time for n, m in enumerate(window, 1)}
    day = assemble(carry_forward(final), readings, times, at(DAY2, ON_TIME_UNTIL))

    assert day.present_carried == {"سلمى", "آية"}   # Aya checked in through Jana
    assert day.today == ["يسرى", "دينا"]            # Yusra's second message is not a duplicate entry
    assert day.late == ["لينا"]
    assert day.listeners == ["بسمة"]
    assert day.new_students == ["هدى"]               # Wafa apologised, so she is nowhere


if __name__ == "__main__":
    tests = [f for name, f in dict(globals()).items() if name.startswith("test_")]
    for test in tests:
        test()
        print("passed:", test.__name__)
    print(f"all {len(tests)} tests passed")
