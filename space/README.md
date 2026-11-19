---
title: Halaqah Attendance List
emoji: 📋
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.32.0
python_version: "3.12"
app_file: app.py
pinned: false
short_description: Turns a WhatsApp export into the day's recitation list
---

# Halaqah attendance list

A password-protected page for the circle's volunteer preparers: upload the WhatsApp group export, get the day's recitation list in the group's Arabic layout.

- Source code and write-up: https://github.com/MdhhMnsr/Halaqah-Attendance
- Uploaded exports are read in memory and deleted straight away; only counts are logged, never names.
