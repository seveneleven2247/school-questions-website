# School Questions Website

A school question board with school-email login, subject tags, searchable questions, file uploads, comments, and helpful/unhelpful voting.

## Features

- Log in with a `@stececile.ca` email address and a 6-digit email code.
- Publish questions with one or more school course tags.
- Upload images, PDFs, text documents, Word files, and PowerPoint files.
- Search questions by title or description.
- Filter questions by tag.
- Comment with text and optional files.
- Vote comments as helpful or unhelpful.
- Comments are ordered by helpful votes first.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5060
```

The SQLite database is created at `data/school_questions.db`. Uploaded files are saved in `uploads/`.

For local email-code testing without SMTP, run with:

```bash
ALLOW_DEV_LOGIN_CODES=true python app.py
```

The login code is printed in the Flask server log.

## Deploy

This is a Flask app with a database and file uploads, so it needs a Python web host instead of GitHub Pages.

The repository includes `render.yaml` for Render Blueprint deployment. It uses:

- `gunicorn app:app` as the production start command.
- `/health` as the health check path.
- A persistent disk mounted at `/var/data` for the SQLite database and uploaded files.
- Render requires a paid service plan for persistent disks. This project uses the `starter` plan in `render.yaml`.

Set these Render environment variables before using email login:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

On Render, create a new Blueprint from this GitHub repository. Render will create the web service and keep the app online at a public URL.
