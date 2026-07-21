import sqlite3
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), 'memory.db')

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
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

def save_turn(user_id, avatar_id, role, content, emotion=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO chat_history (user_id, avatar_id, role, content, emotion, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, avatar_id, role, content, emotion, time.time()))
    conn.commit()
    conn.close()

def get_recent_messages(user_id, avatar_id, limit=20):
    conn = get_connection()
    c = conn.cursor()
    # Get last N messages ordered by id DESC, then reverse to chronological order
    c.execute('''
        SELECT role, content FROM chat_history
        WHERE user_id = ? AND avatar_id = ?
        ORDER BY id DESC
        LIMIT ?
    ''', (user_id, avatar_id, limit))
    rows = c.fetchall()
    conn.close()
    
    # Reverse to make it chronological
    messages = []
    for role, content in reversed(rows):
        messages.append({"role": role, "content": content})
    
    return messages

def clear_history(user_id, avatar_id=None):
    conn = get_connection()
    c = conn.cursor()
    if avatar_id:
        c.execute('''
            DELETE FROM chat_history
            WHERE user_id = ? AND avatar_id = ?
        ''', (user_id, avatar_id))
    else:
        c.execute('''
            DELETE FROM chat_history
            WHERE user_id = ?
        ''', (user_id,))
    conn.commit()
    conn.close()

def get_all_sessions(user_id=None):
    conn = get_connection()
    c = conn.cursor()
    if user_id:
        c.execute('''
            SELECT user_id, MIN(timestamp) as created_at
            FROM chat_history
            WHERE user_id = ?
            GROUP BY user_id
            ORDER BY created_at DESC
        ''', (user_id,))
    else:
        c.execute('''
            SELECT user_id, MIN(timestamp) as created_at
            FROM chat_history
            GROUP BY user_id
            ORDER BY created_at DESC
        ''')
    sessions = []
    rows = c.fetchall()
    
    for row in rows:
        uid, created_at = row
        c.execute('''
            SELECT content FROM chat_history
            WHERE user_id = ? AND role = 'user'
            ORDER BY timestamp ASC
            LIMIT 1
        ''', (uid,))
        res = c.fetchone()
        preview = res[0] if res else "New Chat"
        if len(preview) > 40:
            preview = preview[:37] + "..."
            
        sessions.append({
            "session_id": uid,
            "created_at": created_at,
            "preview": preview
        })
    conn.close()
    return sessions

def get_session_history(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT role, content FROM chat_history
        WHERE user_id = ?
        ORDER BY id ASC
    ''', (user_id,))
    rows = c.fetchall()
    conn.close()
    
    messages = []
    for role, content in rows:
        messages.append({"role": role, "text": content})
    return messages

# ── Admin Analytics ──────────────────────────────────────────────────────────

def get_dashboard_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(DISTINCT user_id) FROM chat_history')
    total_users = c.fetchone()[0] or 0
    
    c.execute('SELECT COUNT(*) FROM chat_history')
    total_messages = c.fetchone()[0] or 0
    
    c.execute('SELECT COUNT(*) FROM chat_history WHERE role = "assistant"')
    total_assistant = c.fetchone()[0] or 0
    
    conn.close()
    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "total_assistant_messages": total_assistant
    }

def get_activity_over_time(days=30):
    conn = get_connection()
    c = conn.cursor()
    # Group by date (YYYY-MM-DD)
    c.execute(f'''
        SELECT date(timestamp, 'unixepoch') as day, COUNT(*) as count
        FROM chat_history
        WHERE timestamp > (strftime('%s', 'now') - (? * 86400))
        GROUP BY day
        ORDER BY day ASC
    ''', (days,))
    rows = c.fetchall()
    conn.close()
    
    return [{"date": row[0], "messages": row[1]} for row in rows]

def get_avatar_usage():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT avatar_id, COUNT(*) as count
        FROM chat_history
        WHERE role = 'assistant'
        GROUP BY avatar_id
        ORDER BY count DESC
    ''')
    rows = c.fetchall()
    conn.close()
    
    return [{"avatar_id": row[0], "count": row[1]} for row in rows]

def get_detailed_logs(limit=100):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT id, user_id, avatar_id, role, content, timestamp
        FROM chat_history
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "id": row[0],
            "user_id": row[1],
            "avatar_id": row[2],
            "role": row[3],
            "content": row[4],
            "timestamp": row[5]
        })
    return logs
