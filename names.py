"""Compare Arabic names written in slightly different ways.

The same sister can be written نسيمة حسن, نسيمه حسن or نسیمہ حسن (Urdu keyboard).
We reduce each name to a plain key before comparing.
"""

import re

# Short vowel marks and other diacritics
DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭـ]")

# Letters that are written differently but mean the same for matching
SAME_LETTER = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه", "ہ": "ه", "ۃ": "ه", "ھ": "ه",
    "ى": "ي", "ی": "ي", "ې": "ي", "ے": "ي",
    "ک": "ك", "گ": "ك",
    "ؤ": "و", "ئ": "ي",
})


def name_key(name: str) -> str:
    key = DIACRITICS.sub("", name).translate(SAME_LETTER).lower()
    return re.sub(r"[^\w]", "", key)  # drop spaces, punctuation, emojis


def same_person(a: str, b: str) -> bool:
    return name_key(a) == name_key(b) and name_key(a) != ""
