"""Lightweight access to the public GitHub latest stable release endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.app_identity import APP_VERSION, PACKAGE_NAME

GITHUB_REPOSITORY = "a-langner/dow2-sm1-texture-painter"
GITHUB_LATEST_RELEASE_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
)
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases"
UPDATE_CHECK_TIMEOUT_SECONDS = 5.0
NO_PUBLISHED_RELEASE_MESSAGE = "No published release is available yet."
LATEST_VERSION_MESSAGE = "You are using the latest version."
UPDATE_FAILURE_MESSAGE = "Unable to check for updates."
VersionParts = tuple[int, ...]


@dataclass(frozen=True)
class GitHubRelease:
    tag_name: object
    html_url: object


class UpdateStatus(Enum):
    LATEST = "latest"
    NEWER = "newer"
    NO_RELEASE = "no_release"
    FAILURE = "failure"


@dataclass(frozen=True)
class UpdateCheckResult:
    status: UpdateStatus
    message: str
    download_url: str | None = None


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


def normalized_version_text(value: str) -> str:
    """Return a validated version without its optional leading ``v``."""
    parse_release_version(value)
    normalized = value.strip()
    return normalized[1:] if normalized[:1].lower() == "v" else normalized


def interpret_latest_release(
    release: GitHubRelease | None,
    current_version: str = APP_VERSION,
) -> UpdateCheckResult:
    """Convert a GitHub response into one safe user-facing update state."""
    if release is None:
        return UpdateCheckResult(
            UpdateStatus.NO_RELEASE,
            NO_PUBLISHED_RELEASE_MESSAGE,
        )
    if not isinstance(release.tag_name, str):
        return UpdateCheckResult(UpdateStatus.FAILURE, UPDATE_FAILURE_MESSAGE)
    try:
        comparison = compare_release_versions(release.tag_name, current_version)
        display_version = normalized_version_text(release.tag_name)
    except ValueError:
        return UpdateCheckResult(UpdateStatus.FAILURE, UPDATE_FAILURE_MESSAGE)
    if comparison <= 0:
        return UpdateCheckResult(UpdateStatus.LATEST, LATEST_VERSION_MESSAGE)
    download_url = (
        release.html_url
        if isinstance(release.html_url, str)
        and release.html_url.startswith("https://")
        else GITHUB_RELEASES_URL
    )
    return UpdateCheckResult(
        UpdateStatus.NEWER,
        f"Version {display_version} is available.",
        download_url,
    )


def check_for_updates() -> UpdateCheckResult:
    """Fetch and interpret an update, hiding network and payload details."""
    try:
        return interpret_latest_release(fetch_latest_stable_release())
    except (OSError, ValueError):
        return UpdateCheckResult(UpdateStatus.FAILURE, UPDATE_FAILURE_MESSAGE)


def fetch_latest_stable_release(
    timeout: float = UPDATE_CHECK_TIMEOUT_SECONDS,
) -> GitHubRelease | None:
    """Fetch GitHub's latest published non-prerelease release without auth."""
    request = Request(
        GITHUB_LATEST_RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{PACKAGE_NAME}/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            document: object = json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if not isinstance(document, dict):
        raise ValueError("GitHub release response must be an object")
    return GitHubRelease(
        tag_name=document.get("tag_name"),
        html_url=document.get("html_url"),
    )
