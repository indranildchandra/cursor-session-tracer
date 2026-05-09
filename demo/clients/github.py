"""
GitHub API client — uses APIKeyAuth directly (old pattern, pre-refactor).
"""

from demo.auth import BearerTokenAuth

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self):
        self.auth = BearerTokenAuth()
        self.base_url = GITHUB_API_BASE

    def get_repo(self, owner: str, repo: str) -> dict:
        # In the live demo, this is where we switch to BearerTokenAuth
        return {
            "owner": owner,
            "repo": repo,
            "auth_headers": self.auth.headers,
            "url": f"{self.base_url}/repos/{owner}/{repo}",
        }

    def list_issues(self, owner: str, repo: str) -> list:
        return []
