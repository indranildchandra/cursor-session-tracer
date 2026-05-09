"""
GitHub API client — post-refactor state.
Uses BearerTokenAuth instead of APIKeyAuth.
"""

from demo_post_changes.auth import BearerTokenAuth

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self):
        self.auth = BearerTokenAuth()
        self.base_url = GITHUB_API_BASE

    def get_repo(self, owner: str, repo: str) -> dict:
        return {
            "owner": owner,
            "repo": repo,
            "auth_headers": self.auth.headers,
            "url": f"{self.base_url}/repos/{owner}/{repo}",
        }

    def list_issues(self, owner: str, repo: str) -> list:
        return []
