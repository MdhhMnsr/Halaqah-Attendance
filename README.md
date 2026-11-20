# Daily Attendance List for an Online Quran Circle: An AI-assisted automation

> **Status: Trial, since 19 November 2026.** Used daily by one volunteer preparer, potential adoption by other volunteers in the future. The accuracy test against past lists is in progress; results below are updated as the trial runs.

## The problem
An online Quran memorisation circle of 65 students meets on Zoom five days a week, **Sunday to Thursday** at 10:30 Madinah time (Friday and Saturday are off days). Before each class, one volunteer, chosen by rotation, builds the order of recitation by hand from the group's WhatsApp chat:

- Read 30–60 attendance messages posted in a 30-minute window, written in English and Arabic, some by Urdu speakers, in many formats (an Arabic attendance card, an English card, a bare name, "X present" sent by someone else);
- Carry forward the students from the last class who were not reached (on Sunday, from Thursday's list), and put them first;
- Remove duplicates, and sort the rest into Today, Late, Listeners and New Students;
- Write every name in Arabic, then repost the whole list about 4 times as more messages come in.

Errors were common because it was done in a hurry just before class. Examples from one day's list: a student listed twice, late arrivals and a listener left out of their sections.

## What I built
A Python tool that turns a WhatsApp Desktop export into the finished list in the group's existing Arabic layout, ready to paste. It runs once a day at 10:25 Madinah time, five minutes before class.

**Design decision: the AI does only the part that needs judgement.**
- **Claude** reads the messages: who is attending, listening, new or absent, and each person's name in Arabic, spelled the way the group already writes it. The answers are returned in a fixed shape (structured output), so a malformed answer stops the run instead of producing a wrong list.
- **Plain code** does everything with an exact rule: the time window (Madinah time, whatever time zone the export came from), the carry-forward rules, ordering, removing duplicates and formatting. These parts are deterministic and tested separately.

**The group's rules, as coded:**
- Class days are Sunday to Thursday. A list for a Friday or Saturday still builds (useful for testing) but is flagged as an off day, and the web page suggests the next class day.
- Attendance messages count from 10:00 Madinah time; after 10:30 they are Late; earlier ones are ignored.
- A student is carried forward only once: from the last class's list, unmarked names in Today's list are carried; ✅ (recited), ❌ (called, no answer) and names an admin marked "left" are dropped; Late, Listeners and New Students are never carried.
- The list uses the group's own template (`list_template.txt`) with the Islamic (Umm al-Qura) date and the day name of the class.

```
WhatsApp export (.zip)
   │
   ├─ parse_chat.py    messages, in Madinah time
   ├─ posted_list.py   yesterday's ticked list → who is carried forward
   ├─ reader.py        Claude labels today's messages   ← the only AI step
   ├─ build_list.py    window, order, duplicates, sections
   ├─ make_list.py     runs it all, saves the list, logs the run
   └─ app.py           the same, as a password-protected web page
```

## Engineering standards
- **Logging:** Every run is recorded (date, messages read, count per section, run time). Claude's reading of each message is saved with a short reason, so any placement can be traced back to its message.
- **Error handling:** Clear messages for an expired key or a refused answer; a warning if yesterday's list has no ticks; the tool prints which list it used for the carry-forward.
- **API cost tracking:** Tokens are printed on every run. About 4 US cents a run (≈ $0.80 a month), with a separate API key so the cost is visible on its own. Re-runs on the same day only send new messages.
- **Tests:** The rules are tested on a made-up sample chat (`tests/test_rules.py`), with no API key needed.

## Privacy and security
- **No real data in this repository.** Members' messages, names and phone numbers stay on the preparer's laptop; `data/`, `output/` and `logs/` are excluded from version control. The sample chat in `samples/` is invented.
- **No unofficial WhatsApp bots,** which break WhatsApp's terms and risk the group's number. The input is WhatsApp's own export.
- **The API key** lives in a local `.env` file (excluded from git) and expires after 30 days.
- **Prompt injection is contained.** Group members' messages are sent to Claude, so a message could try to steer it. Claude can only return labels in a fixed schema and cannot take actions; carried names it returns are checked against the real list in code.

## Results so far
| Measure | Value |
|---|---|
| Agreement with a careful manual reading (first live day) | 28 of 29 messages; the one difference was the tool being right |
| Cost | About 4 US cents a run |
| In daily use since | 19 November 2026 |
| Accuracy against the lists volunteers posted (Jul–Nov 2026) | Being measured |
| Time saved per day | Being measured |

### Usage so far
<!-- usage-table-start -->
| Month | Class days with a list | Attendance messages read | Names placed | From the web page |
|---|---|---|---|---|
| Nov 2026 | 1 | 29 | 30 | 0 |

*Counted from the tool's run logs (counts only). Real runs only: a class day, run on that day, from 19 November 2026. Updated 20 November 2026.*
<!-- usage-table-end -->

Generated by `python usage_table.py --update-readme` from the run logs.

## What I learned
- **The edge cases came from real use, not from planning.** Two exports of the same chat gave the same message different times (9:59 vs 10:00:01), which decided whether a student was on time. A list posted early for the next day was picked up as "yesterday's final list". The group's rule that a student is carried forward only once came out in the first review.
- **Pick the input people already have.** The phone export was slow and its timestamps were rounded; WhatsApp Desktop on the laptop gave a short file with exact times.
- **Keep the model to the judgement call.** Rules that must give the same answer every time (who is late, who is carried) stay in code, where they can be tested and explained.

## Next
- Score the tool against every past list and publish the accuracy.
- Compare a smaller, cheaper model on the same test (accuracy vs cost).
- Let other volunteers run it without a laptop setup. *(Version 1 built: a password-protected web page, see below.)*

## Web page for volunteers (version 1)
`app.py` is a [Gradio](https://www.gradio.app/) page for a Hugging Face Space: a volunteer uploads the WhatsApp export from her own phone and gets the list with a Copy button. No Python or API key needed on her side.
- **Password-protected:** the page and its API refuse every request without the circle's password, and the page will not start if no password is set.
- **Nothing kept:** the uploaded export is read in memory and deleted straight away; the logs hold counts only.
- **Cost guard:** a daily cap on runs, on top of a spend limit on the API key.
- **Any phone:** exports are read whatever the phone's date and time format (day/month or month/day, 24-hour or am/pm).

`python make_space_folder.py` gathers the files the Space needs; the API key and password are set as Space secrets, never in the code.

## Run it
Python 3.10+.

```bash
pip install -r requirements.txt
python tests/test_rules.py
python make_list.py samples/sample-chat.txt 03/11/2026 --readings samples/sample-readings.json
```

The last command builds a list from the sample chat with saved readings, so it needs no API key. For a real run, copy `.env.example` to `.env`, add an Anthropic API key, and point the tool at a WhatsApp export:

```bash
python make_list.py path/to/chat-export.zip 20/11/2026
```

`--phone-utc` sets the time zone of the device that made the export (default 8, Malaysia). On Windows, set `PYTHONIOENCODING=utf-8` so the Arabic prints correctly.
