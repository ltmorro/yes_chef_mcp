"""SQLite database connection pool and schema management.

Uses WAL mode for concurrent readers with a single writer.
Loads sqlite-vec extension for vector similarity search.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import sqlite_vec

_DB_PATH: Path = Path("/data/mealmcp.db")
_connection: sqlite3.Connection | None = None

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Families
CREATE TABLE IF NOT EXISTS families (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    provider        TEXT NOT NULL,
    provider_config TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Members
CREATE TABLE IF NOT EXISTS members (
    id              TEXT PRIMARY KEY,
    family_id       TEXT NOT NULL REFERENCES families(id),
    name            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    is_default      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Recipes
CREATE TABLE IF NOT EXISTS recipes (
    id              TEXT PRIMARY KEY,
    family_id       TEXT NOT NULL REFERENCES families(id),
    name            TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingredients     TEXT NOT NULL DEFAULT '[]',
    instructions    TEXT NOT NULL DEFAULT '',
    servings        INTEGER NOT NULL DEFAULT 1,
    prep_minutes    INTEGER,
    cook_minutes    INTEGER,
    tags            TEXT NOT NULL DEFAULT '[]',
    category        TEXT,
    image_url       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Nutrition (per serving)
CREATE TABLE IF NOT EXISTS nutrition (
    recipe_id       TEXT PRIMARY KEY REFERENCES recipes(id),
    calories        REAL NOT NULL,
    protein_g       REAL NOT NULL,
    carbs_g         REAL NOT NULL,
    fat_g           REAL NOT NULL,
    fiber_g         REAL NOT NULL DEFAULT 0.0,
    sodium_mg       REAL NOT NULL DEFAULT 0.0,
    source          TEXT NOT NULL DEFAULT 'manual',
    confidence      REAL NOT NULL DEFAULT 0.0,
    computed_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Macro targets
CREATE TABLE IF NOT EXISTS macro_targets (
    id              TEXT PRIMARY KEY,
    member_id       TEXT NOT NULL REFERENCES members(id),
    name            TEXT NOT NULL,
    calories        REAL NOT NULL,
    protein_g       REAL NOT NULL,
    carbs_g         REAL NOT NULL,
    fat_g           REAL NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- Macro target day-of-week overrides
CREATE TABLE IF NOT EXISTS macro_target_overrides (
    target_id       TEXT NOT NULL REFERENCES macro_targets(id),
    day_of_week     INTEGER NOT NULL,
    calories        REAL,
    protein_g       REAL,
    carbs_g         REAL,
    fat_g           REAL,
    label           TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (target_id, day_of_week)
);

-- Meal plans
CREATE TABLE IF NOT EXISTS meal_plans (
    id              TEXT PRIMARY KEY,
    family_id       TEXT NOT NULL REFERENCES families(id),
    name            TEXT NOT NULL,
    start_date      TEXT NOT NULL,
    days            INTEGER NOT NULL DEFAULT 7,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Meal slots
CREATE TABLE IF NOT EXISTS meal_slots (
    plan_id         TEXT NOT NULL REFERENCES meal_plans(id),
    day_offset      INTEGER NOT NULL,
    meal_type       TEXT NOT NULL,
    recipe_id       TEXT NOT NULL REFERENCES recipes(id),
    servings        REAL NOT NULL DEFAULT 1.0,
    member_servings TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (plan_id, day_offset, meal_type, recipe_id)
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_recipes_family ON recipes(family_id);
CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);
CREATE INDEX IF NOT EXISTS idx_members_family ON members(family_id);
CREATE INDEX IF NOT EXISTS idx_macro_targets_member ON macro_targets(member_id);
CREATE INDEX IF NOT EXISTS idx_meal_slots_plan ON meal_slots(plan_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_recipe ON nutrition(recipe_id);
"""

FTS_SCHEMA_SQL = """
-- Full-text search virtual table
CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
    recipe_id UNINDEXED,
    name,
    ingredient_names,
    content='',
    tokenize='porter unicode61'
);
"""


def _load_extensions(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension for vector similarity search."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def _init_connection(conn: sqlite3.Connection) -> None:
    """Configure connection settings and ensure schema exists."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    _load_extensions(conn)

    conn.executescript(SCHEMA_SQL)
    conn.executescript(FTS_SCHEMA_SQL)

    # Initialize vec_recipes virtual table for embeddings (384-dim float vectors)
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vec_recipes USING vec0("
            "  recipe_id TEXT PRIMARY KEY,"
            "  embedding float[384]"
            ")"
        )
    except sqlite3.OperationalError:
        # Table already exists with different schema — skip
        pass

    # Track schema version
    row = conn.execute(
        "SELECT COUNT(*) FROM schema_version"
    ).fetchone()
    if row and row[0] == 0:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    conn.commit()


def configure_db_path(path: Path) -> None:
    """Override the default database path. Must be called before get_connection."""
    global _DB_PATH, _connection
    _DB_PATH = path
    _connection = None


def get_connection() -> sqlite3.Connection:
    """Get or create the singleton database connection."""
    global _connection
    if _connection is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _init_connection(_connection)
    return _connection


@contextmanager
def get_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for a database cursor with automatic commit/rollback."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_connection() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
