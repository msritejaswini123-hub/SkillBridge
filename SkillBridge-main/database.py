"""
database.py
===========
Everything SQLite: connection handling, the schema, and small query helpers.

Design notes
------------
* One file database at database/portal.db
* `sqlite3.Row` so rows behave like dicts in Jinja templates (row["title"]).
* Foreign keys are switched ON for every connection (SQLite defaults to OFF).
* EVERY query in this project is parameterised (? placeholders) - no f-string SQL.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "portal.db")


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def connect():
    """Open a connection with sensible defaults. Caller is responsible for closing."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# The Flask app stores one connection per request on `flask.g` (see app.py).
# These helpers work with any connection object, which keeps them testable.

def query_all(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def query_one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def execute(conn, sql, params=()):
    """Run an INSERT/UPDATE/DELETE and return the cursor (has .lastrowid)."""
    cursor = conn.execute(sql, params)
    conn.commit()
    return cursor


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
-- One row per login, whatever the role.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('student', 'company', 'academia')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Role specific detail tables ------------------------------------------------
CREATE TABLE IF NOT EXISTS student_profiles (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    college            TEXT    DEFAULT '',
    qualification      TEXT    DEFAULT '',   -- e.g. 'B.Tech'
    branch             TEXT    DEFAULT '',   -- e.g. 'CSE'
    graduation_year    INTEGER,
    preferred_location TEXT    DEFAULT '',
    min_stipend        INTEGER DEFAULT 0,
    max_stipend        INTEGER DEFAULT 0,
    phone              TEXT    DEFAULT '',
    experience_months  INTEGER DEFAULT 0,
    projects_text      TEXT    DEFAULT '',
    resume_filename    TEXT,
    resume_text        TEXT,
    updated_at         TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    company_name TEXT    NOT NULL,
    industry     TEXT    DEFAULT '',
    website      TEXT    DEFAULT '',
    location     TEXT    DEFAULT '',
    about        TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS academia (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    college_name TEXT    NOT NULL,
    department   TEXT    DEFAULT '',
    contact      TEXT    DEFAULT ''
);

-- Skills -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skills (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category TEXT DEFAULT 'Other'
);

CREATE TABLE IF NOT EXISTS student_skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    source      TEXT    DEFAULT 'manual',   -- 'resume' or 'manual'
    proficiency TEXT    DEFAULT 'Intermediate',
    UNIQUE (student_id, skill_id)
);

-- Internships ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS internships (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    title           TEXT    NOT NULL,
    description     TEXT    DEFAULT '',
    domain          TEXT    DEFAULT 'General',
    location        TEXT    DEFAULT '',
    stipend_min     INTEGER DEFAULT 0,
    stipend_max     INTEGER DEFAULT 0,
    duration_months INTEGER DEFAULT 3,
    qualification   TEXT    DEFAULT 'Any Degree',
    openings        INTEGER DEFAULT 1,
    is_active       INTEGER DEFAULT 1,
    is_demo         INTEGER DEFAULT 0,      -- 1 = seeded demo record
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS internship_skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    skill_id      INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    importance    TEXT    NOT NULL DEFAULT 'required',  -- 'required' or 'preferred'
    UNIQUE (internship_id, skill_id)
);

-- Student <-> internship ----------------------------------------------------
CREATE TABLE IF NOT EXISTS applications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    student_id    INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    status        TEXT    NOT NULL DEFAULT 'Applied',
                  -- Applied / Under Review / Shortlisted / Selected / Rejected
    match_score   REAL    DEFAULT 0,        -- score at the moment of applying
    note          TEXT    DEFAULT '',
    applied_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (internship_id, student_id)
);

CREATE TABLE IF NOT EXISTS saved_internships (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    internship_id INTEGER NOT NULL REFERENCES internships(id) ON DELETE CASCADE,
    saved_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, internship_id)
);

-- Learning resources suggested for missing skills ---------------------------
CREATE TABLE IF NOT EXISTS courses (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id  INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    title     TEXT    NOT NULL,
    provider  TEXT    DEFAULT '',
    url       TEXT    DEFAULT '',
    level     TEXT    DEFAULT 'Beginner',
    duration  TEXT    DEFAULT '',
    is_free   INTEGER DEFAULT 1
);

-- Cached gap analysis: which skills a student is missing, and how many of the
-- internships recommended to them asked for it. Refreshed whenever the student
-- opens Recommendations / Skill Gap; academia reads the aggregate.
CREATE TABLE IF NOT EXISTS skill_gaps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    skill_id      INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    demand_count  INTEGER DEFAULT 1,       -- internships needing it that student lacks
    recorded_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, skill_id)
);

-- Indexes for the joins we run most often ----------------------------------
CREATE INDEX IF NOT EXISTS idx_student_skills_student ON student_skills(student_id);
CREATE INDEX IF NOT EXISTS idx_internship_skills_int  ON internship_skills(internship_id);
CREATE INDEX IF NOT EXISTS idx_internships_company    ON internships(company_id);
CREATE INDEX IF NOT EXISTS idx_applications_student   ON applications(student_id);
CREATE INDEX IF NOT EXISTS idx_applications_int       ON applications(internship_id);
"""


def init_db(conn=None):
    """Create every table (safe to run repeatedly)."""
    own = conn is None
    conn = conn or connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        if own:
            conn.close()


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def get_or_create_skill(conn, name, category="Other"):
    """
    Return the id of a skill, inserting it if it is new.
    `name` should already be normalised by resume_parser.normalize_skill().
    """
    if not name:
        return None
    row = query_one(conn, "SELECT id FROM skills WHERE name = ? COLLATE NOCASE", (name,))
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO skills (name, category) VALUES (?, ?)", (name, category)
    )
    conn.commit()
    return cursor.lastrowid


def student_skill_names(conn, student_id):
    """Canonical skill names a student has, as a list of strings."""
    rows = query_all(
        conn,
        """SELECT s.name FROM student_skills ss
           JOIN skills s ON s.id = ss.skill_id
           WHERE ss.student_id = ?
           ORDER BY s.name""",
        (student_id,),
    )
    return [r["name"] for r in rows]


def internship_skill_map(conn, internship_id):
    """{'required': [names], 'preferred': [names]} for one internship."""
    rows = query_all(
        conn,
        """SELECT s.name, i.importance FROM internship_skills i
           JOIN skills s ON s.id = i.skill_id
           WHERE i.internship_id = ?
           ORDER BY i.importance DESC, s.name""",
        (internship_id,),
    )
    out = {"required": [], "preferred": []}
    for r in rows:
        out.setdefault(r["importance"], []).append(r["name"])
    return out


def all_internship_skills(conn):
    """
    Skills for EVERY internship in one query -> {internship_id: {'required': [...],
    'preferred': [...]}}. Avoids running one query per internship when scoring.
    """
    rows = query_all(
        conn,
        """SELECT i.internship_id, s.name, i.importance
           FROM internship_skills i JOIN skills s ON s.id = i.skill_id""",
    )
    out = {}
    for r in rows:
        entry = out.setdefault(r["internship_id"], {"required": [], "preferred": []})
        entry.setdefault(r["importance"], []).append(r["name"])
    return out


def reset_db():
    """Delete the database file (used by init_db.py --reset and by the tests)."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
