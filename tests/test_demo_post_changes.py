"""
Tests for demo_post_changes/ — the POST-refactor state (expected outcome of the live demo).

Asserts that:
- BearerTokenAuth is used everywhere (Authorization: Bearer header pattern)
- get_current_auth() returns BearerTokenAuth
- No client uses APIKeyAuth
- X-API-Key header is gone from all auth flows
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from demo_post_changes.auth import APIKeyAuth, BearerTokenAuth, get_current_auth
from demo_post_changes.clients.github import GitHubClient
from demo_post_changes.clients.stripe import StripeClient
from demo_post_changes.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# demo_post_changes/auth.py — post-refactor state
# ---------------------------------------------------------------------------

class TestGetCurrentAuthPostRefactor:
    def test_returns_bearer_token_auth(self):
        """POST-refactor: get_current_auth must return BearerTokenAuth."""
        auth = get_current_auth()
        assert isinstance(auth, BearerTokenAuth), (
            "demo_post_changes/ is the post-refactor state. "
            "get_current_auth() must return BearerTokenAuth."
        )

    def test_does_not_return_api_key_auth(self):
        auth = get_current_auth()
        assert not isinstance(auth, APIKeyAuth)

    def test_auth_headers_use_authorization_bearer(self):
        auth = get_current_auth()
        assert "Authorization" in auth.headers
        assert auth.headers["Authorization"].startswith("Bearer ")
        assert "X-API-Key" not in auth.headers


# ---------------------------------------------------------------------------
# demo_post_changes/clients/ — post-refactor state
# ---------------------------------------------------------------------------

class TestGitHubClientPostRefactor:
    def test_uses_bearer_token_auth(self):
        """GitHub client must use BearerTokenAuth in the post-refactor state."""
        gh = GitHubClient()
        assert isinstance(gh.auth, BearerTokenAuth), (
            "GitHubClient should use BearerTokenAuth in demo_post_changes/."
        )

    def test_does_not_use_api_key_auth(self):
        gh = GitHubClient()
        assert not isinstance(gh.auth, APIKeyAuth)

    def test_auth_header_is_authorization_bearer(self):
        gh = GitHubClient()
        assert "Authorization" in gh.auth.headers
        assert "X-API-Key" not in gh.auth.headers

    def test_get_repo_returns_bearer_header(self):
        gh = GitHubClient()
        result = gh.get_repo("torvalds", "linux")
        assert "Authorization" in result["auth_headers"]
        assert "X-API-Key" not in result["auth_headers"]

    def test_get_repo_url_format(self):
        gh = GitHubClient()
        result = gh.get_repo("octocat", "hello-world")
        assert result["url"] == "https://api.github.com/repos/octocat/hello-world"


class TestStripeClientPostRefactor:
    def test_uses_bearer_token_auth(self):
        """Stripe client must use BearerTokenAuth in the post-refactor state."""
        sc = StripeClient()
        assert isinstance(sc.auth, BearerTokenAuth)

    def test_does_not_use_api_key_auth(self):
        sc = StripeClient()
        assert not isinstance(sc.auth, APIKeyAuth)

    def test_auth_header_is_authorization_bearer(self):
        sc = StripeClient()
        assert "Authorization" in sc.auth.headers
        assert "X-API-Key" not in sc.auth.headers

    def test_get_payment_returns_bearer_header(self):
        sc = StripeClient()
        result = sc.get_payment("pi_123")
        assert "Authorization" in result["auth_headers"]
        assert "X-API-Key" not in result["auth_headers"]

    def test_get_payment_url_format(self):
        sc = StripeClient()
        result = sc.get_payment("pi_abc")
        assert result["url"] == "https://api.stripe.com/v1/payment_intents/pi_abc"


# ---------------------------------------------------------------------------
# demo_post_changes/main.py HTTP endpoints — post-refactor state
# ---------------------------------------------------------------------------

class TestDemoPostChangesAppEndpoints:
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
        assert "Authorization" in data["auth_headers"]

    def test_get_repo_no_x_api_key_header(self):
        resp = client.get("/repos/octocat/hello-world")
        assert "X-API-Key" not in resp.json().get("auth_headers", {})

    def test_get_payment(self):
        resp = client.get("/payment/pi_test123")
        assert resp.status_code == 200
        assert resp.json()["payment_id"] == "pi_test123"
        assert "Authorization" in resp.json()["auth_headers"]

    def test_get_payment_no_x_api_key_header(self):
        resp = client.get("/payment/pi_xyz")
        assert "X-API-Key" not in resp.json().get("auth_headers", {})

    def test_auth_validate_returns_bearer_token_auth(self):
        """POST-refactor: /auth/validate must report BearerTokenAuth type."""
        resp = client.get("/auth/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["auth_type"] == "BearerTokenAuth", (
            "demo_post_changes/ is the post-refactor app. "
            "/auth/validate must return auth_type=BearerTokenAuth."
        )

    def test_auth_validate_is_valid_false_without_token(self, monkeypatch):
        """BearerTokenAuth with no token env var should be invalid."""
        monkeypatch.delenv("BEARER_TOKEN", raising=False)
        resp = client.get("/auth/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_auth_validate_is_valid_true_with_token(self, monkeypatch):
        monkeypatch.setenv("BEARER_TOKEN", "live-token-xyz")
        resp = client.get("/auth/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


# ---------------------------------------------------------------------------
# Symmetry check: pre vs post are meaningfully different
# ---------------------------------------------------------------------------

def test_pre_and_post_use_different_auth_types():
    """Smoke check: demo/ and demo_post_changes/ must disagree on auth type."""
    import demo.auth as pre
    import demo_post_changes.auth as post

    assert isinstance(pre.get_current_auth(), pre.APIKeyAuth)
    assert isinstance(post.get_current_auth(), post.BearerTokenAuth)


def test_pre_and_post_header_keys_differ():
    import demo.auth as pre
    import demo_post_changes.auth as post

    pre_headers = pre.get_current_auth().headers
    post_headers = post.get_current_auth().headers

    assert "X-API-Key" in pre_headers
    assert "X-API-Key" not in post_headers
    assert "Authorization" not in pre_headers
    assert "Authorization" in post_headers
