"""
Demo app — small FastAPI app used as the target repo for live demos.
Has a clear architectural seam: API clients using old APIKeyAuth.
"""

from fastapi import FastAPI, HTTPException

from demo.auth import get_current_auth
from demo.clients.github import GitHubClient
from demo.clients.stripe import StripeClient

app = FastAPI(title="Demo App", description="Target repo for cursor-session-tracer live demo")

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
