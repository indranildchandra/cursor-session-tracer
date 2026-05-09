"""
Tests for demo/ — the PRE-refactor state (starting point for the live demo).

Asserts that:
- APIKeyAuth is used everywhere (X-API-Key header pattern)
- get_current_auth() returns APIKeyAuth
- No client uses BearerTokenAuth
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from demo.auth import APIKeyAuth, BearerTokenAuth, get_current_auth
from demo.clients.github import GitHubClient
from demo.clients.stripe import StripeClient
from demo.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# demo/auth.py — pre-refactor state
# ---------------------------------------------------------------------------

class TestAPIKeyAuth:
    def test_headers_use_x_api_key(self):
        auth = APIKeyAuth(api_key="test-key")
        assert auth.headers == {"X-API-Key": "test-key"}

    def test_is_valid_when_key_set(self):
        assert APIKeyAuth(api_key="any-key").is_valid() is True

    def test_is_valid_false_when_no_key_and_no_env(self, monkeypatch):
        # Passing "" falls back to the env var / default; must unset the env var too
        monkeypatch.delenv("API_KEY", raising=False)
        auth = APIKeyAuth(api_key=None)
        # default fallback "demo-key-12345" is still set, so is_valid is True — correct behaviour
        assert auth.is_valid() is True

    def test_is_valid_false_when_env_is_empty(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "")
        auth = APIKeyAuth(api_key=None)
        assert auth.is_valid() is False

    def test_default_key_from_env(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "env-key")
        assert APIKeyAuth().api_key == "env-key"

    def test_default_key_fallback(self, monkeypatch):
        monkeypatch.delenv("API_KEY", raising=False)
        assert APIKeyAuth().api_key == "demo-key-12345"


class TestBearerTokenAuth:
    def test_headers_use_authorization_bearer(self):
        auth = BearerTokenAuth(token="my-token")
        assert auth.headers == {"Authorization": "Bearer my-token"}

    def test_is_valid_when_token_set(self):
        assert BearerTokenAuth(token="tok").is_valid() is True

    def test_is_valid_false_when_empty(self):
        assert BearerTokenAuth(token="").is_valid() is False


class TestGetCurrentAuthPreRefactor:
    def test_returns_api_key_auth(self):
        """PRE-refactor: get_current_auth must return APIKeyAuth, not BearerTokenAuth."""
        auth = get_current_auth()
        assert isinstance(auth, APIKeyAuth), (
            "demo/ is the PRE-refactor state. get_current_auth() must return APIKeyAuth. "
            "If this fails, demo/ was accidentally left in post-refactor state."
        )

    def test_does_not_return_bearer_token_auth(self):
        auth = get_current_auth()
        assert not isinstance(auth, BearerTokenAuth)

    def test_auth_headers_use_x_api_key(self):
        auth = get_current_auth()
        assert "X-API-Key" in auth.headers
        assert "Authorization" not in auth.headers


# ---------------------------------------------------------------------------
# demo/clients/ — pre-refactor state
# ---------------------------------------------------------------------------

class TestGitHubClientPreRefactor:
    def test_uses_api_key_auth(self):
        """GitHub client must use APIKeyAuth in the pre-refactor state."""
        gh = GitHubClient()
        assert isinstance(gh.auth, APIKeyAuth), (
            "GitHubClient should use APIKeyAuth in demo/ (pre-refactor). "
            "Move BearerTokenAuth version to demo_post_changes/."
        )

    def test_auth_header_is_x_api_key(self):
        gh = GitHubClient()
        assert "X-API-Key" in gh.auth.headers

    def test_get_repo_returns_dict(self):
        gh = GitHubClient()
        result = gh.get_repo("torvalds", "linux")
        assert result["owner"] == "torvalds"
        assert result["repo"] == "linux"
        assert "X-API-Key" in result["auth_headers"]

    def test_get_repo_url_format(self):
        gh = GitHubClient()
        result = gh.get_repo("octocat", "hello-world")
        assert result["url"] == "https://api.github.com/repos/octocat/hello-world"


class TestStripeClientPreRefactor:
    def test_uses_api_key_auth(self):
        """Stripe client must use APIKeyAuth in the pre-refactor state."""
        sc = StripeClient()
        assert isinstance(sc.auth, APIKeyAuth), (
            "StripeClient should use APIKeyAuth in demo/ (pre-refactor). "
            "Move BearerTokenAuth version to demo_post_changes/."
        )

    def test_auth_header_is_x_api_key(self):
        sc = StripeClient()
        assert "X-API-Key" in sc.auth.headers

    def test_get_payment_returns_dict(self):
        sc = StripeClient()
        result = sc.get_payment("pi_123")
        assert result["payment_id"] == "pi_123"
        assert "X-API-Key" in result["auth_headers"]

    def test_get_payment_url_format(self):
        sc = StripeClient()
        result = sc.get_payment("pi_abc")
        assert result["url"] == "https://api.stripe.com/v1/payment_intents/pi_abc"


# ---------------------------------------------------------------------------
# demo/main.py HTTP endpoints — pre-refactor state
# ---------------------------------------------------------------------------

class TestDemoAppEndpoints:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_get_repo(self):
        resp = client.get("/repos/torvalds/linux")
        assert resp.status_code == 200
        data = resp.json()
        assert data["owner"] == "torvalds"
        assert data["repo"] == "linux"

    def test_get_payment(self):
        resp = client.get("/payment/pi_test123")
        assert resp.status_code == 200
        assert resp.json()["payment_id"] == "pi_test123"

    def test_auth_validate_returns_api_key_auth(self):
        """PRE-refactor: /auth/validate must report APIKeyAuth type."""
        resp = client.get("/auth/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_type"] == "APIKeyAuth", (
            "demo/ is the pre-refactor app. /auth/validate must return auth_type=APIKeyAuth. "
            "Post-refactor version is in demo_post_changes/."
        )
