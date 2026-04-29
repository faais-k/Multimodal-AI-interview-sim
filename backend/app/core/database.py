"""
MongoDB connection for AI Interview Simulator.

Collections:
  sessions   — one doc per session (metadata + status tracking)
  reports    — final report + analytics (written on interview completion)
  violations — anti-cheat events (one doc per violation event)

Strategy: HYBRID storage.
  - MongoDB stores session metadata and final results (reports, analytics).
  - Flat files remain for in-progress interview_state.json because the
    state machine does many small reads/writes per question that benefit
    from local file I/O speed.
  - Falls back gracefully if MONGODB_URL is not set (flat-file mode only).

Usage:
  await connect_db()    # called in FastAPI lifespan on startup
  await disconnect_db() # called in FastAPI lifespan on shutdown
  db = get_db()         # returns AsyncIOMotorDatabase or None
  db_available()        # True if connected
"""

import os
from typing import Optional

_client = None
_db = None

MONGODB_URL = os.getenv("MONGODB_URL", "")
DB_NAME     = os.getenv("MONGODB_DB", "ai_interview_sim")


async def connect_db() -> None:
    """Connect to MongoDB and create indexes. No-op if MONGODB_URL is unset."""
    global _client, _db

    if not MONGODB_URL:
        print("ℹ️  MONGODB_URL not set — running in flat-file mode only")
        return

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=10,
            minPoolSize=1,
        )
        # Ping to verify connection before declaring success
        await _client.admin.command("ping")
        _db = _client[DB_NAME]

        # Create indexes (idempotent — safe to run on every startup)
        await _db.sessions.create_index("session_id", unique=True)
        await _db.sessions.create_index("created_at")
        await _db.sessions.create_index("status")
        await _db.reports.create_index("session_id", unique=True)
        await _db.violations.create_index("session_id")
        await _db.violations.create_index("logged_at")

        print(f"✅ MongoDB connected: {MONGODB_URL[:40]}… / {DB_NAME}")

    except Exception as e:
        print(f"⚠️  MongoDB connection failed — flat-file mode only: {e}")
        _client = None
        _db = None


async def disconnect_db() -> None:
    """Close the MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        print("🔴 MongoDB disconnected")


def get_db():
    """Return the AsyncIOMotorDatabase instance, or None if not connected."""
    return _db


def db_available() -> bool:
    """True if MongoDB is connected and available."""
    return _db is not None
