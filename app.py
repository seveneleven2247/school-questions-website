import os
import re
import secrets
import sqlite3
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.environ.get("APP_UPLOAD_DIR", BASE_DIR / "uploads"))
DATABASE = DATA_DIR / "school_questions.db"

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "pdf",
    "txt",
    "doc",
    "docx",
    "ppt",
    "pptx",
}

TAGS = [
    "Science 9",
    "Science 10",
    "Physics 11",
    "Physics 12",
    "Biology 11",
    "Biology 12",
    "Chemistry 11",
    "Chemistry 12",
    "Math 9",
    "Math 10",
    "Math 11",
    "Advanced Function",
    "Calculus and Vectors",
    "Calculus",
    "Vector",
    "Data Management",
    "Economic 11",
    "Economic 12",
    "French 9",
    "French 10",
    "French 11",
    "French 12",
    "History 10",
    "History 11",
    "History 12",
    "Philosophy 11",
    "Philosophy 12",
    "Computer Science 11",
    "Computer Science 12",
    "Law 12",
    "Accounting 11",
    "Business Leadership 12",
    "International Business 12",
    "Kinesiology 12",
    "English 9",
    "English 10",
    "English 11",
    "English 12",
]


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-school-questions-secret")
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024

SCHOOL_EMAIL_DOMAIN = os.environ.get("SCHOOL_EMAIL_DOMAIN", "stececile.ca").lower().lstrip("@")
LOGIN_CODE_EXPIRE_MINUTES = int(os.environ.get("LOGIN_CODE_EXPIRE_MINUTES", "10"))
LOGIN_CODE_RESEND_SECONDS = int(os.environ.get("LOGIN_CODE_RESEND_SECONDS", "60"))
LOGIN_CODE_MAX_ATTEMPTS = int(os.environ.get("LOGIN_CODE_MAX_ATTEMPTS", "5"))
STUDENT_EMAIL_LOCAL_RE = re.compile(r"^\d{4}[a-z]_[a-z]+$")


class LoginCodeRateLimitError(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_utc(value):
    return datetime.fromisoformat(value)


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def role_for_email(email):
    normalized = (email or "").strip().lower()
    if normalized == f"2026c_zeng@{SCHOOL_EMAIL_DOMAIN}":
        return "developer"
    if "@" not in normalized:
        return "student"
    local_part, domain = normalized.rsplit("@", 1)
    if domain == SCHOOL_EMAIL_DOMAIN and not STUDENT_EMAIL_LOCAL_RE.fullmatch(local_part):
        return "teacher"
    return "student"


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE COLLATE NOCASE,
                role TEXT NOT NULL DEFAULT 'student' CHECK(role IN ('student', 'teacher', 'developer')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS login_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE,
                purpose TEXT NOT NULL DEFAULT 'login' CHECK(purpose IN ('register', 'login')),
                code_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                used_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS question_tags (
                question_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (question_id, tag),
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_type TEXT NOT NULL CHECK(owner_type IN ('question', 'comment')),
                owner_id INTEGER NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                mime_type TEXT,
                file_size INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS comment_votes (
                comment_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                value INTEGER NOT NULL CHECK(value IN (-1, 1)),
                created_at TEXT NOT NULL,
                PRIMARY KEY (comment_id, user_id),
                FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN email TEXT COLLATE NOCASE")
        if "role" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
        login_code_columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(login_codes)").fetchall()
        }
        if "purpose" not in login_code_columns:
            db.execute("ALTER TABLE login_codes ADD COLUMN purpose TEXT NOT NULL DEFAULT 'login'")
        db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique
            ON users(email)
            WHERE email IS NOT NULL
            """
        )
        users = db.execute("SELECT id, email FROM users WHERE email IS NOT NULL").fetchall()
        for user in users:
            db.execute(
                "UPDATE users SET role = ? WHERE id = ?",
                (role_for_email(user["email"]), user["id"]),
            )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as db:
        user = db.execute(
            "SELECT id, full_name, email, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(user) if user else None


def require_user_id():
    user_id = session.get("user_id")
    if not user_id:
        abort(401)
    return user_id


def require_current_user():
    user = current_user()
    if not user:
        abort(401)
    return user


def require_moderator():
    user = require_current_user()
    if user["role"] not in ("teacher", "developer"):
        abort(403)
    return user


def require_developer():
    user = require_current_user()
    if user["role"] != "developer":
        abort(403)
    return user


def clear_pending_auth():
    for key in (
        "pending_login_user_id",
        "pending_login_email",
        "pending_register_email",
    ):
        session.pop(key, None)


def normalize_school_email(raw_email):
    email = " ".join((raw_email or "").split()).lower()
    if "@" not in email:
        raise ValueError(f"Use your @{SCHOOL_EMAIL_DOMAIN} school email address.")
    local_part, domain = email.rsplit("@", 1)
    if not local_part or domain != SCHOOL_EMAIL_DOMAIN:
        raise ValueError(f"Only @{SCHOOL_EMAIL_DOMAIN} email addresses can log in.")
    return email


def normalize_name_part(name_part):
    if name_part.islower() or name_part.isupper():
        return name_part[:1].upper() + name_part[1:].lower()
    return name_part[:1].upper() + name_part[1:]


def display_name_from_full_name(raw_full_name):
    parts = " ".join((raw_full_name or "").split()).split()
    if len(parts) < 2:
        raise ValueError("Enter your first and last name.")

    first_name = normalize_name_part(parts[0])
    last_initial = next((character.upper() for character in parts[-1] if character.isalpha()), "")
    if not first_name or not any(character.isalpha() for character in first_name) or not last_initial:
        raise ValueError("Enter a valid first and last name.")

    return f"{first_name} {last_initial}"


def normalize_login_identifier(raw_identifier):
    identifier = " ".join((raw_identifier or "").split())
    if not identifier:
        raise ValueError("Enter your school email or account name.")
    if "@" in identifier:
        return normalize_school_email(identifier)
    return identifier


def validate_password(raw_password):
    password = str(raw_password or "")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(password) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    return password


def unique_full_name(db, base_name, exclude_user_id=None):
    query = "SELECT id FROM users WHERE full_name = ? COLLATE NOCASE"
    params = [base_name]
    if exclude_user_id is not None:
        query += " AND id != ?"
        params.append(exclude_user_id)

    existing = db.execute(
        query,
        params,
    ).fetchone()
    if not existing:
        return base_name

    suffix = 2
    while True:
        candidate = f"{base_name} {suffix}"
        query = "SELECT id FROM users WHERE full_name = ? COLLATE NOCASE"
        params = [candidate]
        if exclude_user_id is not None:
            query += " AND id != ?"
            params.append(exclude_user_id)
        existing = db.execute(
            query,
            params,
        ).fetchone()
        if not existing:
            return candidate
        suffix += 1


def find_user_for_login(db, raw_identifier):
    identifier = normalize_login_identifier(raw_identifier)
    if "@" in identifier:
        user = db.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (identifier,),
        ).fetchone()
    else:
        user = db.execute(
            "SELECT * FROM users WHERE full_name = ? COLLATE NOCASE",
            (identifier,),
        ).fetchone()
    if not user:
        raise ValueError("Invalid account name or password.")
    return user


def create_login_code(db, email, purpose):
    now = datetime.now(timezone.utc)
    recent = db.execute(
        """
        SELECT created_at FROM login_codes
        WHERE email = ? AND purpose = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email, purpose),
    ).fetchone()
    if recent:
        created_at = parse_utc(recent["created_at"])
        seconds_since = (now - created_at).total_seconds()
        if seconds_since < LOGIN_CODE_RESEND_SECONDS:
            wait_seconds = int(LOGIN_CODE_RESEND_SECONDS - seconds_since)
            raise LoginCodeRateLimitError(f"Please wait {wait_seconds} seconds before requesting another code.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    cursor = db.execute(
        """
        INSERT INTO login_codes (email, purpose, code_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            email,
            purpose,
            generate_password_hash(code),
            (now + timedelta(minutes=LOGIN_CODE_EXPIRE_MINUTES)).isoformat(timespec="seconds"),
            now.isoformat(timespec="seconds"),
        ),
    )
    return cursor.lastrowid, code


def send_login_code_email(email, code, purpose="login"):
    smtp_host = (os.environ.get("SMTP_HOST") or "").strip()
    smtp_port = int((os.environ.get("SMTP_PORT") or "587").strip())
    smtp_user = (os.environ.get("SMTP_USER") or "").strip()
    smtp_password = "".join((os.environ.get("SMTP_PASSWORD") or "").split())
    smtp_from = (os.environ.get("SMTP_FROM") or smtp_user).strip()

    if not all([smtp_host, smtp_user, smtp_password, smtp_from]):
        if app.debug or os.environ.get("ALLOW_DEV_LOGIN_CODES") == "true":
            app.logger.warning("Login code for %s: %s", email, code)
            return
        raise RuntimeError("Email login is not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM.")

    message = EmailMessage()
    message["Subject"] = f"Your School Questions {purpose} code"
    message["From"] = smtp_from
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Use this 6-digit code to {purpose} on School Questions:",
                "",
                code,
                "",
                f"This code expires in {LOGIN_CODE_EXPIRE_MINUTES} minutes.",
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def send_code_or_error(email, code, login_code_id, purpose):
    try:
        send_login_code_email(email, code, purpose)
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500
    except smtplib.SMTPAuthenticationError as error:
        app.logger.exception(
            "SMTP authentication failed while sending %s code to %s: %s",
            purpose,
            email,
            getattr(error, "smtp_error", error),
        )
        with get_db() as db:
            db.execute("DELETE FROM login_codes WHERE id = ?", (login_code_id,))
        return jsonify({"error": "SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD for the sending email account."}), 500
    except smtplib.SMTPException as error:
        app.logger.exception("SMTP send failed while sending %s code to %s: %s", purpose, email, error)
        with get_db() as db:
            db.execute("DELETE FROM login_codes WHERE id = ?", (login_code_id,))
        return jsonify({"error": "SMTP send failed. Check SMTP_HOST, SMTP_FROM, and the sending email account settings."}), 500
    except Exception:
        app.logger.exception("Unexpected email send failure while sending %s code to %s", purpose, email)
        with get_db() as db:
            db.execute("DELETE FROM login_codes WHERE id = ?", (login_code_id,))
        return jsonify({"error": "Unable to send the login code. Check the Render logs for the exact SMTP error."}), 500
    return None


def normalize_code(raw_code):
    code = "".join(character for character in str(raw_code or "") if character.isdigit())
    if len(code) != 6:
        raise ValueError("Enter the 6-digit code from your email.")
    return code


def verify_login_code(db, email, purpose, raw_code):
    code = normalize_code(raw_code)
    now = datetime.now(timezone.utc)
    login_code = db.execute(
        """
        SELECT * FROM login_codes
        WHERE email = ? AND purpose = ? AND used_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email, purpose),
    ).fetchone()
    if not login_code:
        raise ValueError("Request a new login code first.")
    if parse_utc(login_code["expires_at"]) < now:
        raise ValueError("This code expired. Request a new code.")
    if login_code["attempts"] >= LOGIN_CODE_MAX_ATTEMPTS:
        raise LoginCodeRateLimitError("Too many attempts. Request a new code.")

    db.execute(
        "UPDATE login_codes SET attempts = attempts + 1 WHERE id = ?",
        (login_code["id"],),
    )
    if not check_password_hash(login_code["code_hash"], code):
        raise PermissionError("Invalid code.")
    return login_code


def allowed_file(filename):
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def save_attachments(files, owner_type, owner_id):
    saved = []
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue
        if not allowed_file(file_storage.filename):
            raise ValueError(f"Unsupported file type: {file_storage.filename}")

        original = secure_filename(file_storage.filename) or "upload"
        extension = original.rsplit(".", 1)[1].lower() if "." in original else ""
        stored = f"{uuid.uuid4().hex}.{extension}" if extension else uuid.uuid4().hex
        target = UPLOAD_DIR / stored
        file_storage.save(target)
        saved.append(
            {
                "owner_type": owner_type,
                "owner_id": owner_id,
                "original_name": original,
                "stored_name": stored,
                "mime_type": file_storage.mimetype,
                "file_size": target.stat().st_size,
                "created_at": utc_now(),
            }
        )
    return saved


def validate_files(files):
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue
        if not allowed_file(file_storage.filename):
            raise ValueError(f"Unsupported file type: {file_storage.filename}")


def insert_attachments(db, attachments):
    for attachment in attachments:
        db.execute(
            """
            INSERT INTO attachments (
                owner_type, owner_id, original_name, stored_name, mime_type, file_size, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attachment["owner_type"],
                attachment["owner_id"],
                attachment["original_name"],
                attachment["stored_name"],
                attachment["mime_type"],
                attachment["file_size"],
                attachment["created_at"],
            ),
        )


def delete_attachment_files(db, owner_type, owner_ids):
    for owner_id in owner_ids:
        rows = db.execute(
            "SELECT stored_name FROM attachments WHERE owner_type = ? AND owner_id = ?",
            (owner_type, owner_id),
        ).fetchall()
        for row in rows:
            target = UPLOAD_DIR / row["stored_name"]
            try:
                target.unlink(missing_ok=True)
            except OSError:
                app.logger.warning("Could not delete uploaded file %s", target)
        db.execute(
            "DELETE FROM attachments WHERE owner_type = ? AND owner_id = ?",
            (owner_type, owner_id),
        )


def parse_tags(raw_tags):
    requested = request.form.getlist("tags")
    if raw_tags:
        requested.extend(tag.strip() for tag in raw_tags.split(","))
    clean = []
    tag_lookup = {tag.lower(): tag for tag in TAGS}
    for tag in requested:
        normalized = tag_lookup.get(tag.strip().lower())
        if normalized and normalized not in clean:
            clean.append(normalized)
    return clean


def serialize_attachment(row):
    return {
        "id": row["id"],
        "originalName": row["original_name"],
        "mimeType": row["mime_type"],
        "fileSize": row["file_size"],
        "url": f"/uploads/{row['stored_name']}",
    }


def load_question(question_id):
    user_id = session.get("user_id")
    with get_db() as db:
        question = db.execute(
            """
            SELECT q.id, q.title, q.description, q.created_at, u.full_name AS author
            FROM questions q
            JOIN users u ON u.id = q.user_id
            WHERE q.id = ?
            """,
            (question_id,),
        ).fetchone()
        if not question:
            return None

        tag_rows = db.execute(
            "SELECT tag FROM question_tags WHERE question_id = ? ORDER BY tag",
            (question_id,),
        ).fetchall()
        attachment_rows = db.execute(
            """
            SELECT * FROM attachments
            WHERE owner_type = 'question' AND owner_id = ?
            ORDER BY id
            """,
            (question_id,),
        ).fetchall()
        comment_rows = db.execute(
            """
            SELECT
                c.id,
                c.body,
                c.created_at,
                u.full_name AS author,
                COALESCE(SUM(CASE WHEN cv.value = 1 THEN 1 ELSE 0 END), 0) AS helpful,
                COALESCE(SUM(CASE WHEN cv.value = -1 THEN 1 ELSE 0 END), 0) AS unhelpful,
                COALESCE(MAX(CASE WHEN cv.user_id = ? THEN cv.value END), 0) AS my_vote
            FROM comments c
            JOIN users u ON u.id = c.user_id
            LEFT JOIN comment_votes cv ON cv.comment_id = c.id
            WHERE c.question_id = ?
            GROUP BY c.id
            ORDER BY helpful DESC, unhelpful ASC, c.created_at ASC
            """,
            (user_id or 0, question_id),
        ).fetchall()

        comments = []
        for comment in comment_rows:
            comment_attachments = db.execute(
                """
                SELECT * FROM attachments
                WHERE owner_type = 'comment' AND owner_id = ?
                ORDER BY id
                """,
                (comment["id"],),
            ).fetchall()
            comments.append(
                {
                    "id": comment["id"],
                    "author": comment["author"],
                    "body": comment["body"],
                    "createdAt": comment["created_at"],
                    "helpful": comment["helpful"],
                    "unhelpful": comment["unhelpful"],
                    "myVote": comment["my_vote"],
                    "attachments": [serialize_attachment(row) for row in comment_attachments],
                }
            )

    return {
        "id": question["id"],
        "title": question["title"],
        "description": question["description"],
        "author": question["author"],
        "createdAt": question["created_at"],
        "tags": [row["tag"] for row in tag_rows],
        "attachments": [serialize_attachment(row) for row in attachment_rows],
        "comments": comments,
    }


@app.route("/")
def index():
    return render_template("index.html", tags=TAGS)


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.get("/api/me")
def api_me():
    return jsonify({"user": current_user(), "tags": TAGS})


@app.post("/api/auth/register/request-code")
def api_register_request_code():
    payload = request.get_json(silent=True) or {}
    try:
        email = normalize_school_email(payload.get("email"))
        display_name = display_name_from_full_name(payload.get("fullName"))
        validate_password(payload.get("password"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_db() as db:
        existing = db.execute(
            "SELECT id, password_hash FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if existing and existing["password_hash"]:
            return jsonify({"error": "This email already has an account. Log in instead."}), 409
        try:
            login_code_id, code = create_login_code(db, email, "register")
        except LoginCodeRateLimitError as error:
            return jsonify({"error": str(error)}), 429

    error_response = send_code_or_error(email, code, login_code_id, "register")
    if error_response:
        return error_response

    session["pending_register_email"] = email
    return jsonify({"ok": True, "email": email, "displayName": display_name})


@app.post("/api/auth/register/verify")
def api_register_verify():
    payload = request.get_json(silent=True) or {}
    try:
        email = normalize_school_email(payload.get("email"))
        display_name = display_name_from_full_name(payload.get("fullName"))
        password = validate_password(payload.get("password"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if session.get("pending_register_email") != email:
        return jsonify({"error": "Request a new register code from this browser first."}), 400

    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if existing and existing["password_hash"]:
            return jsonify({"error": "This email already has an account. Log in instead."}), 409
        try:
            login_code = verify_login_code(db, email, "register", payload.get("code"))
        except PermissionError as error:
            return jsonify({"error": "Invalid code."}), 401
        except LoginCodeRateLimitError as error:
            return jsonify({"error": str(error)}), 429
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        if not existing:
            full_name = unique_full_name(db, display_name)
            cursor = db.execute(
                """
                INSERT INTO users (full_name, password_hash, email, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (full_name, generate_password_hash(password), email, role_for_email(email), utc_now()),
            )
            user_id = cursor.lastrowid
        else:
            user_id = existing["id"]
            full_name = unique_full_name(db, display_name, exclude_user_id=user_id)
            db.execute(
                "UPDATE users SET full_name = ?, password_hash = ?, role = ? WHERE id = ?",
                (full_name, generate_password_hash(password), role_for_email(email), user_id),
            )

        db.execute(
            "UPDATE login_codes SET used_at = ? WHERE id = ?",
            (utc_now(), login_code["id"]),
        )

    clear_pending_auth()
    session["user_id"] = user_id
    return jsonify({"user": current_user()})


@app.post("/api/auth/login/start")
def api_login_start():
    payload = request.get_json(silent=True) or {}
    try:
        password = validate_password(payload.get("password"))
    except ValueError:
        return jsonify({"error": "Invalid account name or password."}), 401

    with get_db() as db:
        try:
            user = find_user_for_login(db, payload.get("identifier"))
        except ValueError as error:
            return jsonify({"error": str(error)}), 401
        if not user["password_hash"] or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid account name or password."}), 401
        db.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role_for_email(user["email"]), user["id"]),
        )
        try:
            login_code_id, code = create_login_code(db, user["email"], "login")
        except LoginCodeRateLimitError as error:
            return jsonify({"error": str(error)}), 429

    error_response = send_code_or_error(user["email"], code, login_code_id, "login")
    if error_response:
        return error_response

    session["pending_login_user_id"] = user["id"]
    session["pending_login_email"] = user["email"]
    return jsonify({"ok": True, "email": user["email"], "displayName": user["full_name"]})


@app.post("/api/auth/login/verify")
def api_login_verify():
    payload = request.get_json(silent=True) or {}
    try:
        email = normalize_school_email(payload.get("email"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if session.get("pending_login_email") != email:
        return jsonify({"error": "Enter your account name and password before verifying the code."}), 400

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if not user or not user["password_hash"]:
            return jsonify({"error": "Invalid account. Register first."}), 401
        if session.get("pending_login_user_id") != user["id"]:
            return jsonify({"error": "Enter your account name and password before verifying the code."}), 400
        try:
            login_code = verify_login_code(db, email, "login", payload.get("code"))
        except PermissionError:
            return jsonify({"error": "Invalid code."}), 401
        except LoginCodeRateLimitError as error:
            return jsonify({"error": str(error)}), 429
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

        user_id = user["id"]
        db.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role_for_email(email), user_id),
        )
        db.execute(
            "UPDATE login_codes SET used_at = ? WHERE id = ?",
            (utc_now(), login_code["id"]),
        )

    clear_pending_auth()
    session["user_id"] = user_id
    return jsonify({"user": current_user()})


@app.post("/api/auth/request-code")
def api_request_login_code():
    return jsonify({"error": "Use password login plus email code instead."}), 410


@app.post("/api/auth/verify-code")
def api_verify_login_code():
    return jsonify({"error": "Use password login plus email code instead."}), 410


@app.post("/api/register")
def api_register():
    return jsonify({"error": "Use /api/auth/register/request-code and /api/auth/register/verify instead."}), 410


@app.post("/api/login")
def api_login():
    return jsonify({"error": "Use /api/auth/login/start and /api/auth/login/verify instead."}), 410


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/moderation/overview")
def api_moderation_overview():
    require_moderator()
    with get_db() as db:
        users = db.execute(
            """
            SELECT
                u.id,
                u.full_name,
                u.email,
                u.role,
                u.created_at,
                COUNT(DISTINCT q.id) AS question_count,
                COUNT(DISTINCT c.id) AS comment_count
            FROM users u
            LEFT JOIN questions q ON q.user_id = u.id
            LEFT JOIN comments c ON c.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
            """
        ).fetchall()
        questions = db.execute(
            """
            SELECT
                q.id,
                q.title,
                q.description,
                q.created_at,
                u.full_name AS author,
                u.email AS author_email,
                COUNT(DISTINCT c.id) AS comment_count,
                COUNT(DISTINCT a.id) AS file_count
            FROM questions q
            JOIN users u ON u.id = q.user_id
            LEFT JOIN comments c ON c.question_id = q.id
            LEFT JOIN attachments a ON a.owner_type = 'question' AND a.owner_id = q.id
            GROUP BY q.id
            ORDER BY q.created_at DESC
            LIMIT 100
            """
        ).fetchall()
        comments = db.execute(
            """
            SELECT
                c.id,
                c.body,
                c.created_at,
                c.question_id,
                q.title AS question_title,
                u.full_name AS author,
                u.email AS author_email,
                COALESCE(SUM(CASE WHEN cv.value = 1 THEN 1 ELSE 0 END), 0) AS helpful,
                COALESCE(SUM(CASE WHEN cv.value = -1 THEN 1 ELSE 0 END), 0) AS unhelpful
            FROM comments c
            JOIN questions q ON q.id = c.question_id
            JOIN users u ON u.id = c.user_id
            LEFT JOIN comment_votes cv ON cv.comment_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT 100
            """
        ).fetchall()
    return jsonify(
        {
            "users": [dict(row) for row in users],
            "questions": [dict(row) for row in questions],
            "comments": [dict(row) for row in comments],
        }
    )


@app.delete("/api/moderation/questions/<int:question_id>")
def api_moderation_delete_question(question_id):
    require_moderator()
    with get_db() as db:
        question = db.execute("SELECT id FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not question:
            return jsonify({"error": "Question not found."}), 404
        comment_rows = db.execute("SELECT id FROM comments WHERE question_id = ?", (question_id,)).fetchall()
        delete_attachment_files(db, "question", [question_id])
        delete_attachment_files(db, "comment", [row["id"] for row in comment_rows])
        db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    return jsonify({"ok": True})


@app.delete("/api/moderation/comments/<int:comment_id>")
def api_moderation_delete_comment(comment_id):
    require_moderator()
    with get_db() as db:
        comment = db.execute("SELECT id FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if not comment:
            return jsonify({"error": "Comment not found."}), 404
        delete_attachment_files(db, "comment", [comment_id])
        db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    return jsonify({"ok": True})


@app.post("/api/feedback")
def api_create_feedback():
    user_id = require_user_id()
    payload = request.get_json(silent=True) or {}
    body = (payload.get("body") or "").strip()
    if len(body) < 5:
        return jsonify({"error": "Feedback must be at least 5 characters."}), 400
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO feedback (user_id, body, created_at) VALUES (?, ?, ?)",
            (user_id, body, utc_now()),
        )
    return jsonify({"ok": True, "id": cursor.lastrowid}), 201


@app.get("/api/feedback")
def api_feedback_list():
    require_developer()
    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                f.id,
                f.body,
                f.created_at,
                u.full_name AS author,
                u.email AS author_email,
                u.role AS author_role
            FROM feedback f
            JOIN users u ON u.id = f.user_id
            ORDER BY f.created_at DESC
            """
        ).fetchall()
    return jsonify({"feedback": [dict(row) for row in rows]})


@app.get("/api/questions")
def api_questions():
    selected_tag = request.args.get("tag", "").strip()
    query = request.args.get("q", "").strip()
    params = []
    where = []
    join_tags = ""

    if selected_tag:
        join_tags = "JOIN question_tags filter_tags ON filter_tags.question_id = q.id"
        where.append("filter_tags.tag = ?")
        params.append(selected_tag)
    if query:
        where.append("(q.title LIKE ? OR q.description LIKE ? OR u.full_name LIKE ? OR u.email LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with get_db() as db:
        rows = db.execute(
            f"""
            SELECT
                q.id,
                q.title,
                q.description,
                q.created_at,
                u.full_name AS author,
                COUNT(DISTINCT c.id) AS comment_count
            FROM questions q
            JOIN users u ON u.id = q.user_id
            {join_tags}
            LEFT JOIN comments c ON c.question_id = q.id
            {where_sql}
            GROUP BY q.id
            ORDER BY q.created_at DESC
            """,
            params,
        ).fetchall()

        questions = []
        for row in rows:
            tags = db.execute(
                "SELECT tag FROM question_tags WHERE question_id = ? ORDER BY tag",
                (row["id"],),
            ).fetchall()
            attachments = db.execute(
                """
                SELECT * FROM attachments
                WHERE owner_type = 'question' AND owner_id = ?
                ORDER BY id
                """,
                (row["id"],),
            ).fetchall()
            questions.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "description": row["description"],
                    "author": row["author"],
                    "createdAt": row["created_at"],
                    "commentCount": row["comment_count"],
                    "tags": [tag["tag"] for tag in tags],
                    "attachments": [serialize_attachment(attachment) for attachment in attachments],
                }
            )
    return jsonify({"questions": questions})


@app.post("/api/questions")
def api_create_question():
    user_id = require_user_id()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    tags = parse_tags(request.form.get("tags", ""))
    files = request.files.getlist("files")

    if len(title) < 4:
        return jsonify({"error": "Question title must be at least 4 characters."}), 400
    if len(description) < 10:
        return jsonify({"error": "Description must be at least 10 characters."}), 400
    if not tags:
        return jsonify({"error": "Choose at least one tag."}), 400
    try:
        validate_files(files)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO questions (user_id, title, description, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, title, description, utc_now()),
        )
        question_id = cursor.lastrowid
        for tag in tags:
            db.execute(
                "INSERT INTO question_tags (question_id, tag) VALUES (?, ?)",
                (question_id, tag),
            )
        attachments = save_attachments(files, "question", question_id)
        insert_attachments(db, attachments)

    return jsonify({"question": load_question(question_id)}), 201


@app.get("/api/questions/<int:question_id>")
def api_question_detail(question_id):
    question = load_question(question_id)
    if not question:
        return jsonify({"error": "Question not found."}), 404
    return jsonify({"question": question})


@app.post("/api/questions/<int:question_id>/comments")
def api_create_comment(question_id):
    user_id = require_user_id()
    body = (request.form.get("body") or "").strip()
    files = request.files.getlist("files")

    if len(body) < 2:
        return jsonify({"error": "Comment text is required."}), 400
    try:
        validate_files(files)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_db() as db:
        exists = db.execute("SELECT id FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not exists:
            return jsonify({"error": "Question not found."}), 404

        cursor = db.execute(
            """
            INSERT INTO comments (question_id, user_id, body, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (question_id, user_id, body, utc_now()),
        )
        comment_id = cursor.lastrowid
        attachments = save_attachments(files, "comment", comment_id)
        insert_attachments(db, attachments)

    return jsonify({"question": load_question(question_id)}), 201


@app.post("/api/comments/<int:comment_id>/vote")
def api_vote_comment(comment_id):
    user_id = require_user_id()
    payload = request.get_json(silent=True) or {}
    value = payload.get("value")
    if value not in (-1, 1):
        return jsonify({"error": "Vote must be helpful or unhelpful."}), 400

    with get_db() as db:
        comment = db.execute(
            "SELECT id, question_id FROM comments WHERE id = ?",
            (comment_id,),
        ).fetchone()
        if not comment:
            return jsonify({"error": "Comment not found."}), 404

        current = db.execute(
            "SELECT value FROM comment_votes WHERE comment_id = ? AND user_id = ?",
            (comment_id, user_id),
        ).fetchone()
        if current and current["value"] == value:
            db.execute(
                "DELETE FROM comment_votes WHERE comment_id = ? AND user_id = ?",
                (comment_id, user_id),
            )
        else:
            db.execute(
                """
                INSERT INTO comment_votes (comment_id, user_id, value, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(comment_id, user_id)
                DO UPDATE SET value = excluded.value, created_at = excluded.created_at
                """,
                (comment_id, user_id, value, utc_now()),
            )

    return jsonify({"question": load_question(comment["question_id"])})


@app.errorhandler(401)
def unauthorized(_error):
    return jsonify({"error": "Please log in first."}), 401


@app.errorhandler(403)
def forbidden(_error):
    return jsonify({"error": "You do not have permission to access this area."}), 403


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"error": "Upload is too large. Maximum size is 30 MB."}), 413


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("Unhandled server error", exc_info=error)
    return jsonify({"error": "Server error. Check the Render logs and SMTP settings."}), 500


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5060"))
    app.run(host="0.0.0.0", port=port, debug=True)
