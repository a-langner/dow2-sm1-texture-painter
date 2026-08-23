"""Lightweight access to the public GitHub latest stable release endpoint."""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.request import Request, urlopen

from src.app_identity import APP_VERSION, PACKAGE_NAME

GITHUB_REPOSITORY = "a-langner/dow2-sm1-texture-painter"
GITHUB_LATEST_RELEASE_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
)
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases"
UPDATE_CHECK_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class GitHubRelease:
    tag_name: object
    html_url: object


def fetch_latest_stable_release(
    timeout: float = UPDATE_CHECK_TIMEOUT_SECONDS,
) -> GitHubRelease:
    """Fetch GitHub's latest published non-prerelease release without auth."""
    request = Request(
        GITHUB_LATEST_RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{PACKAGE_NAME}/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        document: object = json.load(response)
    if not isinstance(document, dict):
        raise ValueError("GitHub release response must be an object")
    return GitHubRelease(
        tag_name=document.get("tag_name"),
        html_url=document.get("html_url"),
    )
