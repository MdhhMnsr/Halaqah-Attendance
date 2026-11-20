"""Gather the files the Hugging Face Space needs into space_upload/, ready to drag in.

    python make_space_folder.py

Only code goes in. No .env, no data, no outputs: the API key and password are set as
Secrets in the Space's settings instead.
"""

import shutil
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "space_upload"
CODE = ["app.py", "list_template.txt", "make_list.py", "parse_chat.py", "posted_list.py", "names.py", "reader.py", "build_list.py"]

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()
for name in CODE:
    shutil.copy(HERE / name, OUT / name)
shutil.copy(HERE / "space" / "README.md", OUT / "README.md")            # the Space's settings header
shutil.copy(HERE / "space" / "requirements.txt", OUT / "requirements.txt")

print(f"Ready: {OUT}")
for f in sorted(OUT.iterdir()):
    print("  ", f.name)
