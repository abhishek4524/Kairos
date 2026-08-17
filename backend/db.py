import os
import sys
import time

# Force UTF-8 stdout/stderr — prevents UnicodeEncodeError when spawned by
# Electron on Windows (cp1252 default can't encode emoji in print statements)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    pass  # Python < 3.7 fallback
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# ── Load .env manually (same pattern as llm_agent.py) ────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    with open(_env_path, 'r') as _f:
        for _line in _f:
            _line = _line.strip()
            if '=' in _line and not _line.startswith('#'):
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"\''))

# ── MongoDB Client ────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv('MONGODB_URI', '')
DB_NAME     = os.getenv('MONGODB_DB_NAME', 'nanban')

if MONGODB_URI:
    _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    try:
        _client.admin.command('ping')
        print(f"[MongoDB] ✅ Connected successfully (db={DB_NAME})")
    except ConnectionFailure as _e:
        print(f"[MongoDB] ❌ Connection failed: {_e}")
    _db              = _client[DB_NAME]
    _chat_collection = _db['chat_history']

    # ── Indexes for fast lookups ──────────────────────────────────────────────
    _chat_collection.create_index([('user_id', 1), ('avatar_id', 1), ('timestamp', 1)])
else:
    print("[MongoDB] ⚠️  MONGODB_URI not set — falling back to SQLite")
    _client = None
    _db = None
    _chat_collection = None

# ── SQLite Fallback (local dev / no MONGODB_URI) ──────────────────────────────
import sqlite3

_SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'memory.db')

def _sqlite_conn():
    return sqlite3.connect(_SQLITE_PATH)

def _sqlite_init():
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
    conn.commit()
    conn.close()

if _chat_collection is None:
    _sqlite_init()


# ─────────────────────────────────────────────────────────────────────────────
# Public API — same signatures as before, works with both MongoDB & SQLite
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    """No-op for MongoDB (indexes created at import time). Runs sqlite init if fallback."""
    if _chat_collection is None:
        _sqlite_init()


def save_turn(user_id, avatar_id, role, content, emotion=None):
    if _chat_collection is not None:
        _chat_collection.insert_one({
            'user_id':   user_id,
            'avatar_id': avatar_id,
            'role':      role,
            'content':   content,
            'emotion':   emotion,
            'timestamp': time.time(),
        })
    else:
        conn = _sqlite_conn()
        c = conn.cursor()
        c.execute(
            'INSERT INTO chat_history (user_id, avatar_id, role, content, emotion, timestamp) VALUES (?,?,?,?,?,?)',
            (user_id, avatar_id, role, content, emotion, time.time())
        )
        conn.commit()
        conn.close()


def get_recent_messages(user_id, avatar_id, limit=20):
    if _chat_collection is not None:
        docs = list(
            _chat_collection.find(
                {'user_id': user_id, 'avatar_id': avatar_id},
                {'_id': 0, 'role': 1, 'content': 1}
            ).sort('timestamp', 1).skip(
                max(0, _chat_collection.count_documents({'user_id': user_id, 'avatar_id': avatar_id}) - limit)
            )
        )
        return [{'role': d['role'], 'content': d['content']} for d in docs]
    else:
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
    if _chat_collection is not None:
        query = {'user_id': user_id}
        if avatar_id:
            query['avatar_id'] = avatar_id
        _chat_collection.delete_many(query)
    else:
        conn = _sqlite_conn()
        c = conn.cursor()
        if avatar_id:
            c.execute('DELETE FROM chat_history WHERE user_id=? AND avatar_id=?', (user_id, avatar_id))
        else:
            c.execute('DELETE FROM chat_history WHERE user_id=?', (user_id,))
        conn.commit()
        conn.close()


def get_all_sessions(user_id=None):
    if _chat_collection is not None:
        match = {'user_id': user_id} if user_id else {}
        pipeline = [
            {'$match': match},
            {'$sort': {'timestamp': 1}},
            {'$group': {
                '_id': '$user_id',
                'created_at': {'$min': '$timestamp'},
                'first_user_msg': {'$first': {'$cond': [{'$eq': ['$role', 'user']}, '$content', None]}},
            }},
            {'$sort': {'created_at': -1}},
        ]
        sessions = []
        for doc in _chat_collection.aggregate(pipeline):
            preview = doc.get('first_user_msg') or 'New Chat'
            if preview and len(preview) > 40:
                preview = preview[:37] + '...'
            sessions.append({
                'session_id': doc['_id'],
                'created_at': doc['created_at'],
                'preview':    preview,
            })
        return sessions
    else:
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
    if _chat_collection is not None:
        docs = list(
            _chat_collection.find(
                {'user_id': user_id},
                {'_id': 0, 'role': 1, 'content': 1}
            ).sort('timestamp', 1)
        )
        return [{'role': d['role'], 'text': d['content']} for d in docs]
    else:
        conn = _sqlite_conn()
        c = conn.cursor()
        c.execute('SELECT role, content FROM chat_history WHERE user_id=? ORDER BY id ASC', (user_id,))
        rows = c.fetchall()
        conn.close()
        return [{'role': r, 'text': ct} for r, ct in rows]


# ── Admin Analytics ───────────────────────────────────────────────────────────

def get_dashboard_stats():
    if _chat_collection is not None:
        total_users     = len(_chat_collection.distinct('user_id'))
        total_messages  = _chat_collection.count_documents({})
        total_assistant = _chat_collection.count_documents({'role': 'assistant'})
    else:
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
    if _chat_collection is not None:
        pipeline = [
            {'$match': {'timestamp': {'$gt': cutoff}}},
            {'$group': {
                '_id': {'$dateToString': {
                    'format': '%Y-%m-%d',
                    'date': {'$toDate': {'$multiply': ['$timestamp', 1000]}}
                }},
                'count': {'$sum': 1},
            }},
            {'$sort': {'_id': 1}},
        ]
        return [{'date': d['_id'], 'messages': d['count']} for d in _chat_collection.aggregate(pipeline)]
    else:
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
    if _chat_collection is not None:
        pipeline = [
            {'$match': {'role': 'assistant'}},
            {'$group': {'_id': '$avatar_id', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
        ]
        return [{'avatar_id': d['_id'], 'count': d['count']} for d in _chat_collection.aggregate(pipeline)]
    else:
        conn = _sqlite_conn()
        c = conn.cursor()
        c.execute(
            "SELECT avatar_id, COUNT(*) as count FROM chat_history WHERE role='assistant' GROUP BY avatar_id ORDER BY count DESC"
        )
        rows = c.fetchall()
        conn.close()
        return [{'avatar_id': r[0], 'count': r[1]} for r in rows]


def get_detailed_logs(limit=100):
    if _chat_collection is not None:
        docs = list(
            _chat_collection.find(
                {}, {'_id': 1, 'user_id': 1, 'avatar_id': 1, 'role': 1, 'content': 1, 'timestamp': 1}
            ).sort('timestamp', -1).limit(limit)
        )
        return [{
            'id':        str(d['_id']),
            'user_id':   d.get('user_id'),
            'avatar_id': d.get('avatar_id'),
            'role':      d.get('role'),
            'content':   d.get('content'),
            'timestamp': d.get('timestamp'),
        } for d in docs]
    else:
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
