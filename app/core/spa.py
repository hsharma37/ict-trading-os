"""Shared helper for serving the built React SPA shell (index.html).

Used both by the normal catch-all routes in app/main.py and by the auth
middleware's early short-circuit for SPA routes that collide with a
protected API prefix (see app/core/auth.py's _is_spa_navigation).
"""
import os
from typing import Optional

from fastapi.responses import FileResponse

# index.html must never be cached: it names the current hashed JS/CSS bundle,
# so a stale copy points at an old bundle that no longer exists (blank page).
NOSTORE_HTML_HEADERS = {"Cache-Control": "no-store, must-revalidate"}


def spa_index_response() -> Optional[FileResponse]:
    """Return a FileResponse for the built index.html, or None if not found."""
    cwd = os.getcwd()
    for rel in ["public/index.html", "frontend/dist/index.html"]:
        p = os.path.join(cwd, rel)
        if os.path.exists(p):
            return FileResponse(p, headers=NOSTORE_HTML_HEADERS)
    return None
