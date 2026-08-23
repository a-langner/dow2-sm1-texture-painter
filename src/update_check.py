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
VersionParts = tuple[int, ...]


@dataclass(frozen=True)
class GitHubRelease:
    tag_name: object
    html_url: object


def parse_release_version(value: str) -> VersionParts:
    """Parse a stable dotted numeric version with an optional leading ``v``."""
    if not isinstance(value, str):
        raise ValueError("Release version must be a string")
    normalized = value.strip()
    if normalized[:1].lower() == "v":
        normalized = normalized[1:]
    components = normalized.split(".")
    if not components or any(
        not component.isascii() or not component.isdigit()
        for component in components
    ):
        raise ValueError(f"Invalid release version: {value!r}")
    parts = tuple(int(component) for component in components)
    while len(parts) > 1 and parts[-1] == 0:
        parts = parts[:-1]
    return parts


def compare_release_versions(first: str, second: str) -> int:
    """Compare stable releases numerically, returning -1, 0, or 1."""
    first_parts = parse_release_version(first)
    second_parts = parse_release_version(second)
    width = max(len(first_parts), len(second_parts))
    first_key = first_parts + (0,) * (width - len(first_parts))
    second_key = second_parts + (0,) * (width - len(second_parts))
    return (first_key > second_key) - (first_key < second_key)


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
