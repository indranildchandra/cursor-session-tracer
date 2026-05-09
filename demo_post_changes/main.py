"""
Demo app — post-refactor state.
All API clients now use BearerTokenAuth. This is what the app looks like
AFTER the agent completes the refactoring task shown in the live demo.
"""

from fastapi import FastAPI, HTTPException

from demo_post_changes.auth import get_current_auth
from demo_post_changes.clients.github import GitHubClient
from demo_post_changes.clients.stripe import StripeClient

app = FastAPI(
    title="Demo App (Post-Refactor)",
    description="Target repo after cursor-session-tracer live demo — BearerTokenAuth throughout",
)

github = GitHubClient()
stripe = StripeClient()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/repos/{owner}/{repo}")
def get_repo(owner: str, repo: str):
    """Fetch repo info via GitHub API."""
    try:
        return github.get_repo(owner, repo)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/payment/{payment_id}")
def get_payment(payment_id: str):
    """Fetch payment info via Stripe API."""
    try:
        return stripe.get_payment(payment_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/auth/validate")
def validate_auth():
    """Validate current auth credentials."""
    auth = get_current_auth()
    return {"auth_type": type(auth).__name__, "valid": auth.is_valid()}
