import os
import contextlib
import psycopg2
import psycopg2.extras

_DATABASE_URL = os.getenv("DATABASE_URL")


def _conn():
    return psycopg2.connect(_DATABASE_URL)


def init_db():
    if not _DATABASE_URL:
        return
    try:
        conn_ctx = _conn()
    except psycopg2.OperationalError:
        return
    with conn_ctx as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id        SERIAL PRIMARY KEY,
                event     VARCHAR(100) NOT NULL,
                user_id   VARCHAR(100),
                properties JSONB DEFAULT '{}',
                ts        TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS events_ts_idx    ON events(ts);
            CREATE INDEX IF NOT EXISTS events_user_idx  ON events(user_id);
            CREATE INDEX IF NOT EXISTS events_event_idx ON events(event);
        """)
        conn.commit()


def log_event(event: str, user_id: str | None, properties: dict):
    if not _DATABASE_URL:
        return
    with contextlib.suppress(Exception):
        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO events (event, user_id, properties) VALUES (%s, %s, %s)",
                (event, user_id, psycopg2.extras.Json(properties)),
            )
            conn.commit()


def get_dau(days: int = 30) -> list[dict]:
    if not _DATABASE_URL:
        return []
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT DATE(ts) AS date, COUNT(DISTINCT user_id) AS dau
            FROM events
            WHERE ts >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(ts)
            ORDER BY date
        """, (days,))
        return [dict(r) for r in cur.fetchall()]


def get_retention(days: int = 30) -> list[dict]:
    if not _DATABASE_URL:
        return []
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            WITH first_seen AS (
                SELECT user_id, MIN(DATE(ts)) AS first_date
                FROM events
                WHERE user_id IS NOT NULL
                GROUP BY user_id
            ),
            returned AS (
                SELECT DISTINCT f.user_id, f.first_date
                FROM first_seen f
                JOIN events e ON e.user_id = f.user_id
                WHERE DATE(e.ts) BETWEEN f.first_date + 6 AND f.first_date + 8
            )
            SELECT
                f.first_date,
                COUNT(DISTINCT f.user_id)  AS cohort_size,
                COUNT(DISTINCT r.user_id)  AS retained,
                ROUND(
                    100.0 * COUNT(DISTINCT r.user_id)
                    / NULLIF(COUNT(DISTINCT f.user_id), 0), 1
                ) AS retention_pct
            FROM first_seen f
            LEFT JOIN returned r USING (user_id)
            WHERE f.first_date >= NOW() - INTERVAL '%s days'
            GROUP BY f.first_date
            ORDER BY f.first_date
        """, (days,))
        return [dict(r) for r in cur.fetchall()]


def get_funnel() -> list[dict]:
    if not _DATABASE_URL:
        return []
    steps = [
        'landing_view',
        'signup',
        'login',
        'first_message',
        'upgrade_viewed',
        'upgrade_completed',
    ]
    with _conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT event, COUNT(DISTINCT user_id) AS users
            FROM events
            WHERE event = ANY(%s)
            GROUP BY event
        """, (steps,))
        rows = {r['event']: r['users'] for r in cur.fetchall()}
    return [{'step': s, 'users': rows.get(s, 0)} for s in steps]
