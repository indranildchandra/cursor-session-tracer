"""
Auth for the demo checkout service.

Auth is NOT the focus of this demo — it is already solved with BearerTokenAuth.
The architectural decision under review (see docs/adr/ADR-0001) is about making the
outbound calls *resilient and idempotent*, not about auth.
"""

import os


class BearerTokenAuth:
    """Outbound auth using an Authorization: Bearer header."""

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("BEARER_TOKEN", "demo-token")

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def is_valid(self) -> bool:
        return bool(self.token)


def get_current_auth() -> BearerTokenAuth:
    return BearerTokenAuth()
