"""Web page for preparers: upload a WhatsApp export, get the day's list.

Runs on a Hugging Face Space (Gradio). Settings come from the Space's secrets:
    ANTHROPIC_API_KEY   the API key (a Secret, never a Variable)
    APP_PASSWORD        the password preparers type to open the page
    MAX_RUNS_PER_DAY    optional, default 15: stops runaway use of the key

Privacy: the uploaded export is read in memory and its file deleted straight away.
Only counts are logged (how many messages, how many names per section), never names.
"""

import json
import os
from datetime import datetime, timezone

import gradio as gr

from make_list import MADINAH, load_env_file, make_day_list

load_env_file()  # local testing only; on the Space the secrets are already set

PASSWORD = os.environ.get("APP_PASSWORD", "")
MAX_RUNS_PER_DAY = int(os.environ.get("MAX_RUNS_PER_DAY", "15"))
if not PASSWORD:
    raise SystemExit("APP_PASSWORD is not set, so the page will not start (it must never run open).")

TIMEZONES = {
    "Malaysia / Singapore (UTC+8)": 8,
    "Saudi Arabia / Iraq / Kuwait (UTC+3)": 3,
    "Egypt / Lebanon (UTC+2)": 2,
    "Pakistan (UTC+5)": 5,
    "India (UTC+5:30)": 5.5,
    "Bangladesh (UTC+6)": 6,
    "UK (UTC+0)": 0,
    "Germany / France (UTC+1)": 1,
    "Mauritius / UAE (UTC+4)": 4,
}

runs_today = {"date": "", "count": 0}


def today_in_madinah() -> str:
    return datetime.now(MADINAH).strftime("%d/%m/%Y")


def make_list(upload_path, date_text, tz_label):
    if not upload_path:
        return "", "Please upload the WhatsApp export first (the .zip or .txt file)."
    try:
        # Daily cap, counted in Madinah days
        today = today_in_madinah()
        if runs_today["date"] != today:
            runs_today.update(date=today, count=0)
        if runs_today["count"] >= MAX_RUNS_PER_DAY:
            return "", f"The tool has already been used {MAX_RUNS_PER_DAY} times today. Please try again tomorrow."

        try:
            day = datetime.strptime(date_text.strip(), "%d/%m/%Y").replace(tzinfo=MADINAH)
        except ValueError:
            return "", "Please write the class date as dd/mm/yyyy, for example 20/11/2026."

        runs_today["count"] += 1
        result = make_day_list(upload_path, day, TIMEZONES.get(tz_label, 8))

        # Counts only, for the Space logs
        print(json.dumps({"ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "source": "web", **result.stats}))
        notes = "\n".join(f"- {n}" for n in result.notes)
        return result.text, f"Done. {result.stats['messages_read']} messages read.\n{notes}"

    except SystemExit as e:          # e.g. the API key was refused
        return "", str(e)
    except ValueError as e:          # e.g. no earlier list in the export
        return "", str(e)
    except Exception as e:           # never show a traceback (or anything secret) on the page
        print(f"error: {type(e).__name__}")
        return "", "Something went wrong reading this export. Please check it is a WhatsApp chat export and try again."
    finally:
        if upload_path and os.path.exists(upload_path):
            os.remove(upload_path)   # don't keep anyone's messages


with gr.Blocks(title="Halaqah attendance list", delete_cache=(3600, 3600)) as demo:
    gr.Markdown(
        "## Halaqah attendance list\n"
        "1. In WhatsApp, export the group chat **without media**.\n"
        "2. Upload the file, check the date and your time zone, and press **Make the list**.\n"
        "3. Copy the list and check it before posting it in the group."
    )
    upload = gr.File(label="WhatsApp export (.zip or .txt)", file_types=[".zip", ".txt"], type="filepath")
    with gr.Row():
        date_box = gr.Textbox(label="Class date (dd/mm/yyyy, Madinah)", value=today_in_madinah)
        tz = gr.Dropdown(label="Time zone of the phone/laptop that made the export",
                         choices=list(TIMEZONES), value=list(TIMEZONES)[0])
    go = gr.Button("Make the list", variant="primary")
    status = gr.Markdown()
    output = gr.Textbox(label="The list", lines=30, rtl=True, buttons=["copy"])

    go.click(make_list, inputs=[upload, date_box, tz], outputs=[output, status],
             api_visibility="private", concurrency_limit=1)


if __name__ == "__main__":
    demo.launch(auth=("halaqah", PASSWORD), max_file_size="10mb", ssr_mode=False)
