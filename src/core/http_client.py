import httpx
from src.config.settings import settings
from src.core.logger import get_logger

log = get_logger("core.http_client")


def get_github_client() -> httpx.Client:
    """
    Returns a configured httpx client for GitHub REST API calls.
    Always reads from settings at call time — supports switch_repo() runtime changes.
    """
    log.debug(f"Creating GitHub client for {settings.gh_owner}/{settings.gh_repo}")
    return httpx.Client(
        headers={
            "Authorization": f"Bearer {settings.gh_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        },
        timeout=30.0
    )


def build_github_url(path: str) -> str:
    """
    Builds a full GitHub API URL for the currently active repo.
    Always reads owner/repo from settings — supports runtime switching.
    """
    url = f"https://api.github.com/repos/{settings.gh_owner}/{settings.gh_repo}/{path}"
    log.debug(f"Built GitHub URL: {url}")
    return url
