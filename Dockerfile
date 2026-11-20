# The web page (app.py) as a container for Google Cloud Run.
# Cloud Run builds this straight from the GitHub repo; no secrets are baked in:
# ANTHROPIC_API_KEY, APP_PASSWORD and TEACHER_NAME come from Secret Manager at run time.
FROM python:3.12-slim

WORKDIR /app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY app.py make_list.py parse_chat.py posted_list.py names.py reader.py build_list.py clipboard.py list_template.txt ./

# Print log lines straight away so they show in Cloud Run's logs
ENV PYTHONUNBUFFERED=1

# Cloud Run tells the app which port to use through $PORT (app.py reads it)
CMD ["python", "app.py"]
