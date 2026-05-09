"""
Auth module — uses APIKeyAuth (old pattern).
Target for refactoring to BearerTokenAuth in the live demo.
"""

import os


class APIKeyAuth:
    """Legacy auth using X-API-Key header."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("API_KEY", "demo-key-12345")

    @property
    def headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def is_valid(self) -> bool:
        return bool(self.api_key)


class BearerTokenAuth:
    """New auth pattern using Authorization: Bearer header."""

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("BEARER_TOKEN", "")

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def is_valid(self) -> bool:
        return bool(self.token)


def get_current_auth() -> BearerTokenAuth:
    return BearerTokenAuth()
