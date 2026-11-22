"""Use Claude to read the attendance messages.

Messages come in many shapes: the Arabic attendance card, the English card,
a bare name, "Lina Attendance", "Aya present" sent by someone else,
"listener", "new student", in English, Arabic or Urdu. Plain rules break on
that, so this is the one step where we ask an LLM.

Everything else (time window, order, duplicates, carry-forward) is plain code.
"""

from typing import Literal

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"


class ReadMessage(BaseModel):
    message_number: int
    kind: Literal["attending", "listener", "new_student", "apology_absent", "not_attendance"]
    name_arabic: str        # the sister's name in Arabic script, as the list would show it
    carried_name: str       # exact name from the carried list if it is her, else ""
    note: str               # short reason, for checking the tool's work


class ReadResult(BaseModel):
    messages: list[ReadMessage]


INSTRUCTIONS = """You help prepare the daily attendance list for an online Quran memorisation circle of sisters.
Students post in a WhatsApp group to say they are attending today's class. You get the messages
from the attendance window, numbered. Label every message.

kind:
- attending: she (or someone on her behalf) says she is here to recite today. This includes the
  attendance card (بطاقة الحضور), a bare name, "present", "حاضرة", "Name Attendance".
- listener: she will only listen today (مستمعة, listener, listen only).
- new_student: she says she is new (طالبة جديدة, new student, first day).
- apology_absent: she says she cannot come (اعتذر عن الحضور, can't come today).
- not_attendance: anything else (greetings, stickers, thanks, questions, revision done, admin talk,
  a full list posted by an admin, a deleted message).

name_arabic: the name of the sister the message is about, in Arabic script. The message may be
sent by someone else for her ("Aya present" sent by Jana is about Aya). Write English names in
Arabic letters the way the group writes them. Prefer a spelling from KNOWN NAMES when it is the
same person. Empty string for not_attendance.

carried_name: if this sister is in the CARRIED list (did not recite yesterday), copy that exact
string; otherwise "". Match only when you are confident it is the same person.

note: a few words on how you decided.
"""


def read_messages(
    window: list[tuple[int, str, str]],   # (number, sender, text)
    carried: list[str],
    known_names: list[str],
) -> list[ReadMessage]:
    client = anthropic.Anthropic()

    lines = [f"[{n}] FROM {sender}:\n{text}" for n, sender, text in window]
    prompt = (
        "CARRIED (did not recite yesterday):\n" + "\n".join(carried)
        + "\n\nKNOWN NAMES (spellings used in recent lists):\n" + "، ".join(known_names)
        + "\n\nMESSAGES:\n\n" + "\n\n".join(lines)
    )

    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},
            system=INSTRUCTIONS,
            messages=[{"role": "user", "content": prompt}],
            output_format=ReadResult,
        )
    except anthropic.AuthenticationError:
        raise SystemExit(
            "The API key was refused. It may have expired (the 'halaqah' key lasts 30 days).\n"
            "Create a new key at console.anthropic.com -> API Keys, and replace the line in .env."
        )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"Claude did not return a result (stop_reason={response.stop_reason})")

    usage = response.usage
    print(f"[claude] {usage.input_tokens} input + {usage.output_tokens} output tokens")
    return response.parsed_output.messages


class Spelling(BaseModel):
    name: str           # exactly as given
    name_arabic: str    # the same name in Arabic script


class SpellingResult(BaseModel):
    names: list[Spelling]


SPELLING_INSTRUCTIONS = """You help prepare the daily attendance list for an online Quran circle of sisters.
The list is written in Arabic script, but an admin sometimes types a name in English letters.
For each name given, write it in Arabic letters the way the group would write it. If the same
person appears in KNOWN NAMES, use that spelling. Return every name exactly as given in `name`."""


def arabic_spellings(names: list[str], known_names: list[str]) -> dict[str, str]:
    """Arabic spelling for carried names an admin typed in English letters: {as given: Arabic}."""
    client = anthropic.Anthropic()
    prompt = ("NAMES:\n" + "\n".join(names)
              + "\n\nKNOWN NAMES (spellings used in recent lists):\n" + "، ".join(known_names))
    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=4000,
            output_config={"effort": "low"},
            system=SPELLING_INSTRUCTIONS,
            messages=[{"role": "user", "content": prompt}],
            output_format=SpellingResult,
        )
    except anthropic.AuthenticationError:
        raise SystemExit("The API key was refused. It may have expired (the 'halaqah' key lasts 30 days).")
    if response.parsed_output is None:
        return {}   # keep the names as posted rather than stop the run
    usage = response.usage
    print(f"[claude] spellings: {usage.input_tokens} input + {usage.output_tokens} output tokens")
    return {s.name: s.name_arabic.strip() for s in response.parsed_output.names
            if s.name in names and s.name_arabic.strip()}
