"""Storage adapter: SQLite implementation of the Repository port.

Owns the connection, its lock and the schema. Every other layer exchanges plain
dicts with it, so the tables below hold no meaning outside this file. To run the
system on another store (Postgres, CSV files, a network sync), implement the
same methods on a new class and inject it.
"""
import os
import sqlite3
import threading
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, node TEXT, ts REAL, seq INT, soil_raw INT, temp REAL, hum REAL,
  batt_v REAL, irr_s INT, flow_l REAL, pump_ma INT, rssi INT, vwc REAL, aw REAL);
CREATE INDEX IF NOT EXISTS ix_r ON readings(node, ts);
CREATE TABLE IF NOT EXISTS commands(id INTEGER PRIMARY KEY, node TEXT, ts REAL, run_s INT, reason TEXT, source TEXT, status TEXT);
CREATE INDEX IF NOT EXISTS ix_c ON commands(node, ts);
"""


class SQLiteRepository:
    """Same schema as the original engine; same rows in, same dicts out."""

    def __init__(self, db_path):
        path = db_path if db_path != ':memory:' else None
        if path and os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._lock = threading.RLock()

    # ---- plumbing ----
    @property
    def connection(self):
        return self._db

    @contextmanager
    def lock(self):
        """Serialises a write-then-evaluate run so the dashboard never sees a half-updated bed."""
        with self._lock:
            yield

    @staticmethod
    def _rows(rows):
        return [dict(r) for r in rows]

    # ---- readings ----
    def insert_reading(self, node, ts, seq, soil_raw, temp, hum, batt_v, irr_s, flow_l,
                       pump_ma, rssi, vwc, aw):
        with self._lock:
            self._db.execute(
                'INSERT INTO readings(node,ts,seq,soil_raw,temp,hum,batt_v,irr_s,flow_l,pump_ma,rssi,vwc,aw) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (node, ts, seq, soil_raw, temp, hum, batt_v, irr_s, flow_l, pump_ma, rssi, vwc, aw))
            self._db.commit()

    def readings(self, node, n=96):
        """Last n rows for a node, oldest -> newest."""
        with self._lock:
            rows = self._db.execute('SELECT * FROM readings WHERE node=? ORDER BY ts DESC LIMIT ?',
                                    (node, n)).fetchall()
        return list(reversed(self._rows(rows)))

    def last_irrigation_event(self, node, min_seconds=30):
        row = self._db.execute(
            'SELECT * FROM readings WHERE node=? AND irr_s>=? ORDER BY ts DESC LIMIT 1',
            (node, min_seconds)).fetchone()
        return dict(row) if row else None

    def latest_reading_ts(self):
        row = self._db.execute('SELECT MAX(ts) m FROM readings').fetchone()
        return row['m']

    # ---- watering commands ----
    def insert_command(self, node, ts, run_s, reason, source, status):
        with self._lock:
            cur = self._db.execute(
                'INSERT INTO commands(node,ts,run_s,reason,source,status) VALUES(?,?,?,?,?,?)',
                (node, ts, int(run_s), reason, source, status))
            self._db.commit()
        return cur.lastrowid

    def pending_command(self, node):
        row = self._db.execute("SELECT * FROM commands WHERE node=? AND status='queued' ORDER BY ts LIMIT 1",
                               (node,)).fetchone()
        return dict(row) if row else None

    def latest_sent_command(self, node):
        """Most recent command that already went out the radio (not a queued one)."""
        row = self._db.execute(
            "SELECT * FROM commands WHERE node=? AND status!='queued' ORDER BY ts DESC LIMIT 1",
            (node,)).fetchone()
        return dict(row) if row else None

    def mark_command_sent(self, command_id, ts):
        with self._lock:
            self._db.execute("UPDATE commands SET status='sent', ts=? WHERE id=?", (ts, command_id))
            self._db.commit()

    def recent_commands(self, limit=30):
        """Newest first; the dashboard's activity feed."""
        rows = self._db.execute('SELECT * FROM commands ORDER BY ts DESC LIMIT ?', (limit,)).fetchall()
        return self._rows(rows)
