"""SQLite persistence for inquiries, quotes and payments (single backend worker)."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
from threading import RLock
import time

LOCK = RLock()
_connection = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS inquiries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  name TEXT NOT NULL,
  company TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL,
  phone TEXT NOT NULL DEFAULT '',
  message TEXT NOT NULL DEFAULT '',
  brief TEXT NOT NULL DEFAULT '{}',
  transcript TEXT NOT NULL DEFAULT '[]',
  admin_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id INTEGER NOT NULL REFERENCES inquiries(id),
  token TEXT NOT NULL UNIQUE,
  created_at REAL NOT NULL,
  title TEXT NOT NULL,
  items TEXT NOT NULL,
  total INTEGER NOT NULL,
  deposit INTEGER NOT NULL,
  schedule TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'sent',
  order_id TEXT,
  payment_key TEXT,
  paid_at REAL,
  payment_method TEXT
);
CREATE TABLE IF NOT EXISTS consult_sessions (
  id TEXT PRIMARY KEY,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  lang TEXT NOT NULL DEFAULT 'ko',
  messages TEXT NOT NULL DEFAULT '[]',
  brief TEXT NOT NULL DEFAULT '{}',
  user_turns INTEGER NOT NULL DEFAULT 0,
  inquiry_id INTEGER
);
CREATE INDEX IF NOT EXISTS consult_sessions_updated ON consult_sessions(updated_at);
CREATE TABLE IF NOT EXISTS inquiry_files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  inquiry_id INTEGER NOT NULL REFERENCES inquiries(id),
  created_at REAL NOT NULL,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  size INTEGER NOT NULL
);
"""


def data_dir():
    configured = os.environ.get("DATA_DIR")
    return Path(configured) if configured else Path(__file__).resolve().parents[1] / "data"


def connect(path=None):
    """Open (or reopen, e.g. in tests) the database."""
    global _connection
    with LOCK:
        if _connection is not None:
            _connection.close()
        target = Path(path) if path else data_dir() / "site.db"
        target.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(target, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.executescript(SCHEMA)
        columns = {row[1] for row in _connection.execute("PRAGMA table_info(inquiries)")}
        if "lang" not in columns:  # added with the English site; existing rows are Korean
            _connection.execute("ALTER TABLE inquiries ADD COLUMN lang TEXT NOT NULL DEFAULT 'ko'")
        _connection.commit()
        return _connection


def db():
    return _connection or connect()


def row_dict(row, json_fields=()):
    if row is None:
        return None
    value = dict(row)
    for field in json_fields:
        value[field] = json.loads(value[field])
    return value


def create_inquiry(name, company, email, phone, message, brief, transcript, lang="ko"):
    with LOCK:
        cursor = db().execute(
            "INSERT INTO inquiries (created_at, name, company, email, phone, message, brief, transcript, lang) VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), name, company, email, phone, message, json.dumps(brief, ensure_ascii=False),
             json.dumps(transcript, ensure_ascii=False), lang))
        db().commit()
        return cursor.lastrowid


def list_inquiries():
    with LOCK:
        rows = db().execute(
            "SELECT i.id, i.created_at, i.status, i.name, i.company, i.email, i.brief, i.lang, "
            "(SELECT q.status FROM quotes q WHERE q.inquiry_id = i.id ORDER BY q.id DESC LIMIT 1) AS quote_status, "
            "(SELECT COUNT(*) FROM inquiry_files f WHERE f.inquiry_id = i.id) AS file_count "
            "FROM inquiries i ORDER BY i.id DESC LIMIT 200").fetchall()
        return [row_dict(row, ("brief",)) for row in rows]


def get_inquiry(inquiry_id):
    with LOCK:
        inquiry = row_dict(db().execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone(), ("brief", "transcript"))
        if inquiry:
            inquiry["quotes"] = [row_dict(q, ("items",)) for q in db().execute(
                "SELECT * FROM quotes WHERE inquiry_id = ? ORDER BY id DESC", (inquiry_id,)).fetchall()]
            inquiry["files"] = [dict(f) for f in db().execute(
                "SELECT id, original_name, size, created_at FROM inquiry_files WHERE inquiry_id = ? ORDER BY id", (inquiry_id,)).fetchall()]
        return inquiry


def delete_inquiry(inquiry_id):
    """Used only to roll back an inquiry whose attachments failed to save."""
    with LOCK:
        db().execute("DELETE FROM inquiry_files WHERE inquiry_id = ?", (inquiry_id,))
        db().execute("DELETE FROM inquiries WHERE id = ?", (inquiry_id,))
        db().commit()


def add_file(inquiry_id, original_name, stored_name, size):
    with LOCK:
        db().execute("INSERT INTO inquiry_files (inquiry_id, created_at, original_name, stored_name, size) VALUES (?,?,?,?,?)",
                     (inquiry_id, time.time(), original_name, stored_name, size))
        db().commit()


def get_file(file_id):
    with LOCK:
        return row_dict(db().execute("SELECT * FROM inquiry_files WHERE id = ?", (file_id,)).fetchone())


def update_inquiry(inquiry_id, status=None, admin_note=None):
    with LOCK:
        if status is not None:
            db().execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, inquiry_id))
        if admin_note is not None:
            db().execute("UPDATE inquiries SET admin_note = ? WHERE id = ?", (admin_note, inquiry_id))
        db().commit()


# ---------- AI 상담 기록 ----------
# 접수 여부와 관계없이 AI 상담 대화를 보관한다. 상담창에 보관 사실과 기간을 알리고,
# 보관 기간(CONSULT_RETENTION_DAYS, 기본 90일)이 지나면 자동으로 지운다.

def consult_retention_days():
    try:
        return max(1, int(os.environ.get("CONSULT_RETENTION_DAYS") or 90))
    except ValueError:
        return 90


def purge_consults():
    cutoff = time.time() - consult_retention_days() * 86400
    with LOCK:
        removed = db().execute("DELETE FROM consult_sessions WHERE updated_at < ?", (cutoff,)).rowcount
        db().commit()
        return removed


def save_consult(session_id, lang, messages, brief):
    """Upsert one chat session with its full transcript (the client sends the whole history each turn)."""
    now = time.time()
    turns = sum(m["role"] == "user" for m in messages)
    with LOCK:
        row = db().execute("SELECT brief FROM consult_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            db().execute("INSERT INTO consult_sessions (id, created_at, updated_at, lang, messages, brief, user_turns) VALUES (?,?,?,?,?,?,?)",
                         (session_id, now, now, lang, json.dumps(messages, ensure_ascii=False), json.dumps(brief or {}, ensure_ascii=False), turns))
        else:
            kept = brief or json.loads(row["brief"])  # 요약은 한 번 만들어지면 이후 턴에서 없어도 유지
            db().execute("UPDATE consult_sessions SET updated_at = ?, lang = ?, messages = ?, brief = ?, user_turns = ? WHERE id = ?",
                         (now, lang, json.dumps(messages, ensure_ascii=False), json.dumps(kept, ensure_ascii=False), turns, session_id))
        db().commit()
    purge_consults()


def link_consult(session_id, inquiry_id):
    with LOCK:
        db().execute("UPDATE consult_sessions SET inquiry_id = ? WHERE id = ?", (inquiry_id, session_id))
        db().commit()


def list_consults(days=30, query=""):
    since = time.time() - days * 86400
    with LOCK:
        rows = db().execute("SELECT * FROM consult_sessions WHERE updated_at >= ? ORDER BY updated_at DESC LIMIT 500", (since,)).fetchall()
    result = []
    needle = query.strip().lower()
    for row in rows:
        messages = json.loads(row["messages"])
        if needle and not any(needle in m["content"].lower() for m in messages):
            continue
        brief = json.loads(row["brief"])
        first = next((m["content"] for m in messages if m["role"] == "user"), "")
        result.append({"id": row["id"], "created_at": row["created_at"], "updated_at": row["updated_at"], "lang": row["lang"],
                       "user_turns": row["user_turns"], "first": first[:160], "title": brief.get("title", ""),
                       "has_brief": bool(brief), "inquiry_id": row["inquiry_id"]})
    return result


def consult_stats(days=30):
    since = time.time() - days * 86400
    with LOCK:
        row = db().execute("SELECT COUNT(*) AS total, SUM(brief != '{}') AS briefs, SUM(inquiry_id IS NOT NULL) AS submitted, "
                           "AVG(user_turns) AS turns FROM consult_sessions WHERE updated_at >= ?", (since,)).fetchone()
    return {"days": days, "total": row["total"] or 0, "briefs": row["briefs"] or 0, "submitted": row["submitted"] or 0,
            "avg_turns": round(row["turns"] or 0, 1), "retention_days": consult_retention_days()}


def get_consult(session_id):
    with LOCK:
        return row_dict(db().execute("SELECT * FROM consult_sessions WHERE id = ?", (session_id,)).fetchone(), ("messages", "brief"))


def delete_consult(session_id):
    with LOCK:
        removed = db().execute("DELETE FROM consult_sessions WHERE id = ?", (session_id,)).rowcount
        db().commit()
        return removed


def create_quote(inquiry_id, title, items, total, deposit, schedule, note):
    token = secrets.token_urlsafe(18)
    with LOCK:
        db().execute(
            "INSERT INTO quotes (inquiry_id, token, created_at, title, items, total, deposit, schedule, note) VALUES (?,?,?,?,?,?,?,?,?)",
            (inquiry_id, token, time.time(), title, json.dumps(items, ensure_ascii=False), total, deposit, schedule, note))
        db().execute("UPDATE inquiries SET status = 'quoted' WHERE id = ?", (inquiry_id,))
        db().commit()
    return token


def get_quote(token):
    with LOCK:
        quote = row_dict(db().execute("SELECT * FROM quotes WHERE token = ?", (token,)).fetchone(), ("items",))
        if quote:
            inquiry = db().execute("SELECT name, company, email, phone, lang FROM inquiries WHERE id = ?", (quote["inquiry_id"],)).fetchone()
            quote["customer"] = dict(inquiry) if inquiry else {}
        return quote


def set_order(token, order_id):
    with LOCK:
        db().execute("UPDATE quotes SET order_id = ? WHERE token = ? AND status != 'paid'", (order_id, token))
        db().commit()


def mark_paid(token, payment_key, method):
    with LOCK:
        db().execute("UPDATE quotes SET status = 'paid', payment_key = ?, paid_at = ?, payment_method = ? WHERE token = ?",
                     (payment_key, time.time(), method, token))
        db().execute("UPDATE inquiries SET status = 'deposit_paid' WHERE id = (SELECT inquiry_id FROM quotes WHERE token = ?)", (token,))
        db().commit()
