"""
Input validation helpers shared across all route handlers.

validate_session_id() must be called in every route that accepts a session_id
before any file I/O, to prevent path traversal attacks where a malformed
session_id such as "../other_session" resolves to a sibling directory.
"""

import re
from fastapi import HTTPException

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_session_id(session_id: str) -> str:
    """Ensure session_id is a valid UUID4. Raises HTTP 400 if not.

    Prevents path traversal attacks via malformed session_id values.
    All route handlers must call this before using session_id in any Path.

    Returns session_id unchanged if valid.
    """
    if not session_id or not _UUID4_RE.match(session_id.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id. Must be a UUID4 (xxxxxxxx-xxxx-4xxx-xxxx-xxxxxxxxxxxx).",
        )
    return session_id
