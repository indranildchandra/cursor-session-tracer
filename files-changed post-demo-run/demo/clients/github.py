"""
GitHub client — routes mutating calls through demo/resilience.py (ADR-0001).
"""

from demo.auth import get_current_auth
from demo.resilience import ResilientTransport, resilient_call

GITHUB_API_BASE = "https://api.github.com"


class GitHubError(Exception):
    """Raised when the (simulated) GitHub API call fails."""


class GitHubClient:
    def __init__(self):
        self.auth = get_current_auth()
        self.base_url = GITHUB_API_BASE
        self.receipts: list[dict] = []

    def _create_receipt_once(
        self, owner: str, repo: str, order_id: str, amount_cents: int
    ) -> dict:
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

    def create_receipt_issue(
        self,
        owner: str,
        repo: str,
        order_id: str,
        amount_cents: int,
        *,
        transport: ResilientTransport | None = None,
    ) -> dict:
        """Create a receipt as a GitHub issue. Idempotent on order_id via the transport."""
        return resilient_call(
            dependency=self.base_url,
            idempotency_key=f"receipt:{order_id}",
            operation=lambda: self._create_receipt_once(owner, repo, order_id, amount_cents),
            transport=transport,
        )

    def get_repo(self, owner: str, repo: str) -> dict:
        return {
            "owner": owner,
            "repo": repo,
            "url": f"{self.base_url}/repos/{owner}/{repo}",
            "auth_headers": self.auth.headers,
        }
