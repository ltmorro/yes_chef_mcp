"""Async SQLite database connection and schema management.

Uses aiosqlite for non-blocking async access. WAL mode for concurrent
readers with a single writer. Loads sqlite-vec extension for vector search.
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
import sqlite_vec

_DB_PATH: Path = Path("/data/yes_chef_mcp.db")
_schema_initialized: bool = False

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
    tokenize='porter unicode61'
);
"""


def _load_extensions(conn: aiosqlite.Connection) -> None:
    """Load sqlite-vec extension for vector similarity search."""
    raw: sqlite3.Connection = conn._conn  # noqa: SLF001
    raw.enable_load_extension(True)
    sqlite_vec.load(raw)
    raw.enable_load_extension(False)


async def _init_connection(conn: aiosqlite.Connection) -> None:
    """Configure connection settings and ensure schema exists.

    PRAGMAs and extensions are set on every connection. Schema DDL only
    runs once per DB path (guarded by ``_schema_initialized``).
    """
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA busy_timeout=5000")

    _load_extensions(conn)

    global _schema_initialized
    if not _schema_initialized:
        await conn.executescript(SCHEMA_SQL)
        await conn.executescript(FTS_SCHEMA_SQL)

        # Initialize vec_recipes virtual table for embeddings (384-dim float vectors)
        with contextlib.suppress(sqlite3.OperationalError):
            await conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS vec_recipes USING vec0("
                "  recipe_id TEXT PRIMARY KEY,"
                "  embedding float[384]"
                ")"
            )

        # Track schema version
        async with conn.execute("SELECT COUNT(*) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 0:
                await conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
        await conn.commit()
        _schema_initialized = True


def configure_db_path(path: Path) -> None:
    """Override the default database path. Must be called before get_connection."""
    global _DB_PATH, _schema_initialized
    _DB_PATH = path
    _schema_initialized = False


async def get_connection() -> aiosqlite.Connection:
    """Create a new async database connection.

    Each caller gets its own connection — no shared singleton.
    Connections are lightweight in WAL mode; aiosqlite runs each
    on its own background thread so they don't block the event loop.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = aiosqlite.Row
    await _init_connection(conn)
    return conn


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager for a database connection with auto-commit/rollback."""
    conn = await get_connection()
    try:
        yield conn
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()
