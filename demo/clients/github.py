"""
GitHub client — NAIVE starting state (the target of the live demo).

Creates a receipt issue after a successful charge. Like the Stripe client, the
call is unguarded: no retry, no idempotency. A duplicate receipt is annoying
rather than dangerous, but the same resilience seam (docs/adr/ADR-0001) covers it.
"""

from demo.auth import get_current_auth

GITHUB_API_BASE = "https://api.github.com"


class GitHubError(Exception):
    """Raised when the (simulated) GitHub API call fails."""


class GitHubClient:
    def __init__(self):
        self.auth = get_current_auth()
        self.base_url = GITHUB_API_BASE
        self.receipts: list[dict] = []

    def create_receipt_issue(self, owner: str, repo: str, order_id: str, amount_cents: int) -> dict:
        """Create a receipt as a GitHub issue. MUTATING, not idempotent."""
        receipt = {
            "issue_number": len(self.receipts) + 1,
            "order_id": order_id,
            "title": f"Receipt for order {order_id}",
            "body": f"Charged {amount_cents} cents.",
            "url": f"{self.base_url}/repos/{owner}/{repo}/issues",
            "auth_headers": self.auth.headers,
        }
        self.receipts.append(receipt)
        return receipt

    def get_repo(self, owner: str, repo: str) -> dict:
        return {
            "owner": owner,
            "repo": repo,
            "url": f"{self.base_url}/repos/{owner}/{repo}",
            "auth_headers": self.auth.headers,
        }
