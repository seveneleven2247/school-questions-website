import os
import sqlite3
import uuid
from datetime import datetime, timezone
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


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


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
            """
        )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as db:
        user = db.execute(
            "SELECT id, full_name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(user) if user else None


def require_user_id():
    user_id = session.get("user_id")
    if not user_id:
        abort(401)
    return user_id


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


@app.post("/api/register")
def api_register():
    payload = request.get_json(silent=True) or {}
    full_name = " ".join((payload.get("fullName") or "").split())
    password = payload.get("password") or ""
    if len(full_name) < 2:
        return jsonify({"error": "Full name is required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    try:
        with get_db() as db:
            cursor = db.execute(
                "INSERT INTO users (full_name, password_hash, created_at) VALUES (?, ?, ?)",
                (full_name, generate_password_hash(password), utc_now()),
            )
            session["user_id"] = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this full name already exists."}), 409

    return jsonify({"user": current_user()})


@app.post("/api/login")
def api_login():
    payload = request.get_json(silent=True) or {}
    full_name = " ".join((payload.get("fullName") or "").split())
    password = payload.get("password") or ""
    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE full_name = ? COLLATE NOCASE",
            (full_name,),
        ).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Full name or password is incorrect."}), 401
    session["user_id"] = user["id"]
    return jsonify({"user": current_user()})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


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
        where.append("(q.title LIKE ? OR q.description LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])

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


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"error": "Upload is too large. Maximum size is 30 MB."}), 413


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5060"))
    app.run(host="0.0.0.0", port=port, debug=True)
