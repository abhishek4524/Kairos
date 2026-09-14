import os
import sys
import time
import sqlite3

# Force UTF-8 stdout/stderr — prevents UnicodeEncodeError when spawned by
# Electron on Windows (cp1252 default can't encode emoji in print statements)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass  # Python < 3.7 fallback

# ── Persistent user-data directory (writable even in Program Files installs) ──
def _get_data_dir() -> str:
    """Return a writable data directory for Kairos. Checks env override first."""
    override = os.environ.get("KAIROS_DATA_DIR")
    if override:
        path = override.strip().strip('"\'')
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        path = os.path.join(appdata, "Kairos")
    else:
        path = os.path.expanduser("~/.kairos")
    os.makedirs(path, exist_ok=True)
    return path

# ── Local SQLite Storage ──────────────────────────────────────────────────────
_SQLITE_PATH = os.path.join(_get_data_dir(), 'memory.db')

def _sqlite_conn():
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn

def init_db():
    """Initializes local SQLite tables and indexes."""
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            avatar_id TEXT DEFAULT 'avatar.vrm',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            emotion TEXT,
            timestamp REAL NOT NULL
        )
    ''')
    try:
        c.execute("ALTER TABLE chat_history ADD COLUMN avatar_id TEXT DEFAULT 'avatar.vrm'")
    except sqlite3.OperationalError:
        pass

    # Create indexes for high-speed queries
    c.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_avatar ON chat_history (user_id, avatar_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chat_timestamp ON chat_history (timestamp)")

    conn.commit()
    conn.close()
    print(f"[Database] ✅ Local SQLite storage active at: {_SQLITE_PATH}")

# Auto-initialize on module load
init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def save_turn(user_id, avatar_id, role, content, emotion=None):
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute(
        'INSERT INTO chat_history (user_id, avatar_id, role, content, emotion, timestamp) VALUES (?,?,?,?,?,?)',
        (user_id, avatar_id, role, content, emotion, time.time())
    )
    conn.commit()
    conn.close()


def get_recent_messages(user_id, avatar_id, limit=20):
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute(
        'SELECT role, content FROM chat_history WHERE user_id=? AND avatar_id=? ORDER BY id DESC LIMIT ?',
        (user_id, avatar_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return [{'role': r, 'content': ct} for r, ct in reversed(rows)]


def clear_history(user_id, avatar_id=None):
    conn = _sqlite_conn()
    c = conn.cursor()
    if avatar_id:
        c.execute('DELETE FROM chat_history WHERE user_id=? AND avatar_id=?', (user_id, avatar_id))
    else:
        c.execute('DELETE FROM chat_history WHERE user_id=?', (user_id,))
    conn.commit()
    conn.close()


def get_all_sessions(user_id=None):
    conn = _sqlite_conn()
    c = conn.cursor()
    if user_id:
        c.execute(
            'SELECT user_id, MIN(timestamp) as created_at FROM chat_history WHERE user_id=? GROUP BY user_id ORDER BY created_at DESC',
            (user_id,)
        )
    else:
        c.execute('SELECT user_id, MIN(timestamp) as created_at FROM chat_history GROUP BY user_id ORDER BY created_at DESC')
    rows = c.fetchall()
    sessions = []
    for uid, created_at in rows:
        c.execute(
            "SELECT content FROM chat_history WHERE user_id=? AND role='user' ORDER BY timestamp ASC LIMIT 1",
            (uid,)
        )
        res = c.fetchone()
        preview = res[0] if res else 'New Chat'
        if len(preview) > 40:
            preview = preview[:37] + '...'
        sessions.append({'session_id': uid, 'created_at': created_at, 'preview': preview})
    conn.close()
    return sessions


def get_session_history(user_id):
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute('SELECT role, content FROM chat_history WHERE user_id=? ORDER BY id ASC', (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{'role': r, 'text': ct} for r, ct in rows]


# ── Admin Analytics ───────────────────────────────────────────────────────────

def get_dashboard_stats():
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(DISTINCT user_id) FROM chat_history')
    total_users = c.fetchone()[0] or 0
    c.execute('SELECT COUNT(*) FROM chat_history')
    total_messages = c.fetchone()[0] or 0
    c.execute('SELECT COUNT(*) FROM chat_history WHERE role="assistant"')
    total_assistant = c.fetchone()[0] or 0
    conn.close()
    return {
        'total_users':             total_users,
        'total_messages':          total_messages,
        'total_assistant_messages': total_assistant,
    }


def get_activity_over_time(days=30):
    cutoff = time.time() - days * 86400
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute(
        "SELECT date(timestamp, 'unixepoch') as day, COUNT(*) as count FROM chat_history WHERE timestamp > ? GROUP BY day ORDER BY day ASC",
        (cutoff,)
    )
    rows = c.fetchall()
    conn.close()
    return [{'date': r[0], 'messages': r[1]} for r in rows]


def get_avatar_usage():
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute(
        "SELECT avatar_id, COUNT(*) as count FROM chat_history WHERE role='assistant' GROUP BY avatar_id ORDER BY count DESC"
    )
    rows = c.fetchall()
    conn.close()
    return [{'avatar_id': r[0], 'count': r[1]} for r in rows]


def get_detailed_logs(limit=100):
    conn = _sqlite_conn()
    c = conn.cursor()
    c.execute(
        'SELECT id, user_id, avatar_id, role, content, timestamp FROM chat_history ORDER BY timestamp DESC LIMIT ?',
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return [{
        'id': r[0], 'user_id': r[1], 'avatar_id': r[2],
        'role': r[3], 'content': r[4], 'timestamp': r[5],
    } for r in rows]

